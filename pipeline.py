"""Preparación, evaluación temporal y scoring reproducibles del caso The Look."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import numpy as np
import pandas as pd
import joblib
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (average_precision_score, precision_recall_curve,
    precision_score, recall_score, f1_score, brier_score_loss, confusion_matrix)

NUM = ['declared_items','observed_items','basket_value','unique_products',
       'unique_categories','events_30d','sessions_30d','product_views_30d']
CAT = ['main_category','last_traffic_source','last_browser',
       'purchase_dayofweek','purchase_hour','purchase_month']
FEATURES = NUM + CAT

def prepare_data(path, cutoff='2025-02-14'):
    """El CSV es salida SQL as-of. Un corte distinto exige regenerarlo en BigQuery."""
    df = pd.read_csv(path)
    df['first_order_at'] = pd.to_datetime(df.first_order_at, utc=True, format='mixed')
    df['cutoff_ts'] = pd.to_datetime(df.cutoff_ts, utc=True, format='mixed')
    c = pd.Timestamp(cutoff, tz='UTC')
    if not df.cutoff_ts.eq(c).all():
        raise ValueError('El corte solicitado no coincide con el CSV. Regenerar SQL.')
    if df.user_id.isna().any() or df.user_id.duplicated().any():
        raise ValueError('Debe existir una fila por cliente con ID no nulo.')
    if not df.first_order_at.lt(c).all():
        raise ValueError('Hay primeras compras fuera del corte.')
    mature = df.first_order_at + pd.Timedelta(days=60) < c
    if not df.target.notna().eq(mature).all():
        raise ValueError('Etiquetas inconsistentes con la madurez de 60 días.')
    if not df.loc[mature,'target'].isin([0,1]).all():
        raise ValueError('Target no binario.')
    # Coerción estable de categorías, sin aprender de validación o test.
    for col in CAT:
        df[col] = df[col].fillna('SIN_DATO').astype(str)
    for col in NUM:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        if df[col].dropna().lt(0).any():
            raise ValueError(f'Variable negativa: {col}')
    return df.sort_values(['first_order_at','user_id']).reset_index(drop=True)

def temporal_split(df, validation_start='2024-01-01',
                   validation_end='2024-07-01', test_start='2024-09-01'):
    """Embargo de 60 días: todas las etiquetas previas maduraron al evaluar."""
    v0,v1,t0 = [pd.Timestamp(x,tz='UTC') for x in
                 [validation_start,validation_end,test_start]]
    end_label = df.first_order_at + pd.Timedelta(days=60)
    train = df.loc[df.target.notna() & end_label.lt(v0)].copy()
    val = df.loc[df.target.notna() & df.first_order_at.ge(v0) &
                 df.first_order_at.lt(v1) & end_label.lt(t0)].copy()
    test = df.loc[df.target.notna() & df.first_order_at.ge(t0)].copy()
    for name,part in [('train',train),('validation',val),('test',test)]:
        if len(part)<100 or part.target.nunique()!=2:
            raise ValueError(f'{name}: tamaño o clases insuficientes.')
    assert (train.first_order_at+pd.Timedelta(days=60)).max()<val.first_order_at.min()
    assert (val.first_order_at+pd.Timedelta(days=60)).max()<test.first_order_at.min()
    return train,val,test

def build_model(kind, features=FEATURES):
    nums=[x for x in NUM if x in features]
    cats=[x for x in CAT if x in features]
    preprocessing=ColumnTransformer([
        ('num',Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True)),
                         ('scale',StandardScaler())]),nums),
        ('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cats)],
        remainder='drop')
    if kind=='baseline': model=DummyClassifier(strategy='prior')
    elif kind=='logistic': model=LogisticRegression(max_iter=1500,C=1.0,random_state=42)
    elif kind=='boosting': model=HistGradientBoostingClassifier(max_iter=120,
        max_leaf_nodes=15,learning_rate=.07,l2_regularization=5,random_state=42)
    else: raise ValueError(kind)
    return Pipeline([('prepare',preprocessing),('model',model)])

def evaluate(y,p,threshold=.5):
    y=np.asarray(y,dtype=int); p=np.asarray(p)
    pred=p>=threshold
    # Empates resueltos por orden temporal/ID del dataset, no por target.
    k=max(1,int(np.ceil(.20*len(y))))
    ix=np.argsort(-p,kind='stable')[:k]
    tied=np.ptp(p)==0
    # Un score constante no ordena clientes: reportar expectativa aleatoria,
    # no un top arbitrario que herede el orden temporal del archivo.
    top_precision=float(y.mean()) if tied else float(y[ix].mean())
    top_recall=k/len(y) if tied else float(y[ix].sum()/y.sum())
    return dict(n=len(y),prevalence=float(y.mean()),ap=float(average_precision_score(y,p)),
        precision=float(precision_score(y,pred,zero_division=0)),
        recall=float(recall_score(y,pred,zero_division=0)),
        f1=float(f1_score(y,pred,zero_division=0)),
        brier=float(brier_score_loss(y,p)),threshold=float(threshold),
        precision_top20=top_precision,recall_top20=top_recall,
        lift_top20=top_precision/float(y.mean()),
        confusion_matrix=confusion_matrix(y,pred).tolist())

def generate_predictions(model, frame, model_version, threshold, outpath):
    p=model.predict_proba(frame[FEATURES])[:,1]
    out=frame[['user_id','first_order_at','cutoff_ts']].copy()
    out['probability_repurchase_60d']=p
    out['prediction']= (p>=threshold).astype(int)
    out['model_version']=model_version
    out=out.sort_values(['probability_repurchase_60d','user_id'],ascending=[False,True])
    if out.user_id.duplicated().any() or not out.probability_repurchase_60d.between(0,1).all():
        raise ValueError('Predicciones inválidas.')
    Path(outpath).parent.mkdir(parents=True,exist_ok=True)
    # Sobrescribir snapshot, nunca append: misma ejecución no duplica clientes.
    out.to_csv(outpath,index=False)
    return out

def run_pipeline(data_path, output_dir, cutoff='2025-02-14', **split_params):
    root=Path(output_dir); root.mkdir(parents=True,exist_ok=True)
    df=prepare_data(data_path,cutoff)
    train,val,test=temporal_split(df,**split_params)
    candidates={}; validation={}; thresholds={}
    for kind in ['baseline','logistic','boosting']:
        model=build_model(kind).fit(train[FEATURES],train.target.astype(int))
        p=model.predict_proba(val[FEATURES])[:,1]
        precision,recall,ts=precision_recall_curve(val.target,p)
        f=2*precision[:-1]*recall[:-1]/np.maximum(precision[:-1]+recall[:-1],1e-12)
        threshold=float(ts[np.argmax(f)])
        thresholds[kind]=threshold
        validation[kind]=evaluate(val.target,p,threshold)
        candidates[kind]=model
    # Selección únicamente en validación, entre clasificadores entrenados.
    selected=max(['logistic','boosting'],key=lambda k:validation[k]['ap'])
    test_metrics={}; predictions={}
    for kind,model in candidates.items():
        p=model.predict_proba(test[FEATURES])[:,1]
        predictions[kind]=p
        test_metrics[kind]=evaluate(test.target,p,thresholds[kind])
    version=f'{selected}_v1_cutoff_{cutoff}'
    artifact={'pipeline':candidates[selected],'features':FEATURES,
              'threshold':thresholds[selected],'model_version':version}
    joblib.dump(artifact,root/'model_evaluated.joblib')
    scoring=df[df.target.isna()].copy()
    # Replay al instante de primera compra, no campaña actual sobre datos de 2025.
    scored=generate_predictions(candidates[selected],scoring,version,
                               thresholds[selected],root/'predictions_replay.csv')
    digest=hashlib.sha256(Path(data_path).read_bytes()).hexdigest()
    summary={
      'cutoff':cutoff,'data_sha256':digest,'python':platform.python_version(),
      'sklearn':sklearn.__version__,'n_clients':len(df),'n_mature':int(df.target.notna().sum()),
      'n_censored':len(scoring),'overall_rate':float(df.target.mean()),
      'non_cancelled_rate':float(df.target_non_cancelled.mean()),
      'basket_missing_rate':float(df.basket_value.isna().mean()),
      'events_zero_rate':float(df.events_30d.eq(0).mean()),
      'selected':selected,'validation':validation,'test':test_metrics,
      'splits':{name:{'n':len(part),'start':str(part.first_order_at.min()),
           'end':str(part.first_order_at.max()),'rate':float(part.target.mean())}
          for name,part in [('train',train),('validation',val),('test',test)]}}
    # Permutación a nivel de variable original en VALIDACIÓN, sin tocar selección del test.
    rng=np.random.default_rng(42); base=validation[selected]['ap']; importance=[]
    sample=val.sample(min(6000,len(val)),random_state=42)
    base_sample=average_precision_score(sample.target,candidates[selected].predict_proba(sample[FEATURES])[:,1])
    for col in FEATURES:
        x=sample[FEATURES].copy(); x[col]=rng.permutation(x[col].to_numpy())
        ap=average_precision_score(sample.target,candidates[selected].predict_proba(x)[:,1])
        importance.append({'feature':col,'ap_drop':float(base_sample-ap)})
    pd.DataFrame(importance).sort_values('ap_drop',ascending=False).to_csv(root/'importance_validation.csv',index=False)
    summary['sensitivity_test_non_cancelled']=evaluate(test.target_non_cancelled,predictions[selected],thresholds[selected])
    # Ablación: comprueba cuánto aporta la navegación frente al contexto del pedido.
    reduced=[x for x in FEATURES if x not in ['events_30d','sessions_30d','product_views_30d','last_traffic_source','last_browser']]
    ablation=build_model(selected,reduced).fit(train[reduced],train.target.astype(int))
    summary['ablation_no_events_validation_ap']=float(average_precision_score(val.target,ablation.predict_proba(val[reduced])[:,1]))
    # Gate ilustrativo fijado por política, no optimizado contra el test.
    # La aprobación de negocio requiere además un piloto y costos reales.
    summary['promotion_policy']={'validation_ap_relative_gain_min':.10,'validation_lift_top20_min':1.20}
    summary['approved_for_production']=bool(
        validation[selected]['ap']>=validation['baseline']['ap']*1.10
        and validation[selected]['lift_top20']>=1.20)
    rng=np.random.default_rng(2026); lifts=[]
    y=test.target.to_numpy(); p=predictions[selected]
    for _ in range(400):
        ix=rng.integers(0,len(y),len(y)); yy=y[ix]; pp=p[ix]
        top=np.argsort(-pp,kind='stable')[:int(np.ceil(.2*len(yy)))]
        lifts.append(float(yy[top].mean()/yy.mean()))
    summary['test_lift_top20_bootstrap_95']=np.quantile(lifts,[.025,.975]).tolist()
    summary['bootstrap_note']='Bootstrap iid de clientes, descriptivo y condicionado al modelo fijo; no captura dependencia temporal ni incertidumbre de entrenamiento.'
    (root/'metrics.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    test_out=test[['user_id','first_order_at','target']].copy()
    for kind,p in predictions.items(): test_out[kind]=p
    test_out.to_csv(root/'test_predictions.csv',index=False)
    return df,train,val,test,candidates,predictions,summary,scored

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',default='data/model_base.csv.gz')
    parser.add_argument('--output',default='reports/run')
    parser.add_argument('--cutoff',default='2025-02-14')
    args=parser.parse_args()
    *_,summary,_=run_pipeline(args.data,args.output,args.cutoff)
    print(json.dumps(summary,indent=2,ensure_ascii=False))
