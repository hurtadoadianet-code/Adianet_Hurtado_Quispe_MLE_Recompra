# Recompra a 60 días

**Adianet Hurtado Quispe · Caso Machine Learning Engineer**

Análisis de recompra para The Look, un ecommerce ficticio. El objetivo es estimar si un cliente creará otra orden en los 60 días posteriores a su primera orden.

El [notebook](Adianet_Hurtado_Quispe_Recompra.ipynb) contiene las consultas SQL, el análisis, la comparación de modelos y cinco figuras con resultados visibles. La presentación se entregó por correo.

## Resultados

La base tiene 79.634 clientes. De ellos, 70.741 cuentan con 60 días completos de seguimiento y 5.094 recompraron, una tasa del 7,20%. Los 8.893 restantes quedan fuera del entrenamiento y la evaluación por seguimiento incompleto.

El modelo de árboles se seleccionó por su resultado en validación. En la prueba final obtuvo AP de 0,1563, frente a 0,1593 de la referencia, y lift de 1,003 al priorizar el 20% de clientes. Estos resultados no respaldan su activación en producción. La recomendación es mejorar las señales disponibles y comprobar su estabilidad antes de realizar un piloto comercial.

## Ejecución

Desde la raíz del repositorio:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
jupyter notebook Adianet_Hurtado_Quispe_Recompra.ipynb
```

Ejecutar las celdas en orden. La extracción comprimida permite reproducir el análisis sin credenciales de BigQuery. También se puede ejecutar el pipeline:

```powershell
python pipeline.py --data model_base.csv.gz --output reports/run --cutoff 2025-02-14
```

Las salidas se guardan en `reports/run`. Reejecutar reemplaza las predicciones del lote y no agrega clientes duplicados.

## Contenido

| Archivo | Función |
|---|---|
| `Adianet_Hurtado_Quispe_Recompra.ipynb` | Análisis y evaluación ejecutados |
| `pipeline.py` | Preparación, entrenamiento y predicción |
| `00_schema_and_states.sql` | Estructura de tablas y estados de órdenes |
| `01_quality.sql` | Controles de claves, nulos, duplicados y cruces |
| `02_model_base.sql` | Construcción de una fila por cliente |
| `model_base.csv.gz` | Base derivada para reproducir el análisis |
| `source_quality.json` | Resultados de controles en el origen |
| `metrics.json` | Métricas y períodos de evaluación |
| `model_candidate.joblib` | Modelo candidato y transformaciones |
| `sample_predictions.csv` | Muestra de probabilidades |
| `arquitectura_aws.md` | Diseño de operación en AWS |
| `requirements.txt` | Dependencias |

## Decisiones de datos y evaluación

- Fuente: `bussiness-case-tyc.bussiness_case_ecommerce`.
- Corte exclusivo: 14/02/2025 a las 00:00 UTC, para excluir el último día parcial.
- Recompra: otra orden creada después de la primera y hasta 60 días después. Los ítems de la misma orden no cuentan como compras adicionales.
- El objetivo principal incluye todos los estados de orden. Se reporta una sensibilidad que excluye futuras cancelaciones. Para predecir compras pagadas se necesitaría acordar otra definición y contar con historial de pagos y estados.
- Las variables utilizan información disponible al crear la primera orden. Se excluyeron 78.579 ítems registrados después de su orden de las variables históricas.
- Las transformaciones se ajustan solo con entrenamiento. La selección del modelo y del umbral usa validación, y la prueba final mide el desempeño posterior.
- Entrenamiento con etiquetas maduras antes de enero de 2024, validación de enero a junio y prueba desde septiembre, respetando 60 días de madurez entre bloques.

El catálogo se considera estático y se asume disponibilidad al tiempo del evento. Una implementación real requiere verificar tiempos de ingesta e historia de cambios. Los datos son del ecommerce ficticio del ejercicio y no incluyen nombres, correos, direcciones ni IP. Las predicciones representan una evaluación histórica, no una lista de campaña vigente.

## Arquitectura

La propuesta parte de fuentes en S3 y utiliza Glue para transformación y controles, SageMaker para entrenamiento y predicción por lotes, y S3/Athena para entregar los resultados. EventBridge y Step Functions programan el flujo. El monitoreo revisa calidad de datos y desempeño cuando maduran las etiquetas. El código se versiona en GitHub. El diseño incluye una alternativa de integración con Snowflake.

No se desplegaron recursos cloud. Los supuestos, limitaciones y referencias oficiales están detallados en el notebook y en `arquitectura_aws.md`.
