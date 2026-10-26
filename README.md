# Recompra a 60 días

**Adianet Hurtado Quispe · Caso Machine Learning Engineer · Octubre de 2026**

Solución para The Look, un ecommerce ficticio. Incluye SQL en BigQuery, notebook
ejecutado con cinco figuras, preparación y predicción automatizadas en Python,
comparación con referencia sencilla, evaluación temporal y diseño AWS.

## Presentación

- [Presentación ejecutiva PDF](Adianet_Hurtado_Quispe_Presentacion_Entrega.pdf)
- [PowerPoint editable con notas](Adianet_Hurtado_Quispe_Presentacion_Entrega.pptx)
- [Notebook ejecutado](Adianet_Hurtado_Quispe_Recompra.ipynb)

## Resultado principal

79.634 clientes, 70.741 con seguimiento completo y 7,20% de recompra global.
Se excluyen de la evaluación 8.893 clientes sin 60 días completos. El candidato
seleccionado en validación no mejora de forma útil el ranking en test: AP 0,1563
frente a referencia 0,1593 y lift top20 de 1,003. Se recomienda mejorar la señal
y validar nuevas cohortes antes de activar una campaña. No se inventaron resultados.

## Cómo ejecutar

Clonar o descargar este repositorio, abrir una terminal en su raíz y ejecutar:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
jupyter notebook Adianet_Hurtado_Quispe_Recompra.ipynb
```

Ejecutar todas las celdas en orden. Los archivos de Python, la base comprimida
y los controles están en la raíz para facilitar la ejecución. No se necesitan
credenciales para reproducir el modelo con la extracción local.

Alternativa sin notebook:

```powershell
python pipeline.py --data model_base.csv.gz --output reports/run --cutoff 2025-02-14
```

Las predicciones reemplazan el snapshot sin duplicar clientes. Modelo y
transformaciones se guardan juntos, con parámetros, hash y versión.

## SQL y decisiones

00_schema_and_states.sql inspecciona estructura y estados. 01_quality.sql verifica
claves, duplicados, nulos y cruces. 02_model_base.sql construye una fila por cliente.
Fuente: bussiness-case-tyc.bussiness_case_ecommerce. Corte exclusivo 14/02/2025 UTC.

El objetivo implementado es nueva orden creada en (primera orden, primera orden
+60 días], con todos los estados. Se reporta sensibilidad sin futuras cancelaciones.
Las variables usan solo ítems y eventos disponibles en la primera orden. Se
excluyeron 78.579 ítems posteriores a su orden de las variables históricas.
El catálogo se considera estático y se asume disponibilidad al tiempo del evento.
En producción se necesita historia de catálogo, estados y tiempo de ingesta.

Entrenamiento con etiquetas maduras antes de enero 2024, validación enero-junio
2024 y test desde septiembre 2024, con 60 días de madurez entre bloques.
La selección del modelo y umbral usa validación. El test solo mide resultados.
No se usan IDs, próxima compra, estados finales o datos personales como variables.

## Arquitectura y contenido adicional

arquitectura_aws.md explica fuentes S3, transformación Glue, programación con
EventBridge/Step Functions, entrenamiento y scoring SageMaker, almacenamiento
de predicciones, monitoreo y versionamiento con GitHub. Es un diseño, no un despliegue.

El ZIP adjunto contiene la estructura completa del proyecto original, pruebas,
gráficos individuales, documentación y resultados adicionales. Las pruebas del
proyecto completo pasaron, y el notebook contiene diez celdas ejecutadas y cinco figuras.

Los datos derivados corresponden al ecommerce ficticio del ejercicio y no
incluyen nombres, correos, direcciones ni IP. Las predicciones son replay
histórico al instante de primera orden, no una campaña vigente. El modelo
serializado es un candidato no aprobado para producción.

Referencias oficiales y fuentes están en el notebook y la documentación.
