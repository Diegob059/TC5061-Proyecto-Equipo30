# Reporte de Interpretación Técnica de Data Drift (Evidently AI)
## Proyecto MiBici Guadalajara — MLOps Equipo 30
**Modelo Evaluado:** `mibici-equipo30-p2-riesgo` (Clasificación Multiclase de Riesgo Operativo a 2 Horas)  
**Fecha de Auditoría:** Noviembre 2026  
**Herramienta de Monitoreo:** Evidently AI (`evidently==0.7.23`)

---

## 1. Resumen Ejecutivo

En el marco del **Entregable 8 (Monitoreo y Reporte de Drift en Producción)**, se implementó una auditoría exhaustiva de observabilidad de datos sobre las **17 variables predictoras** del modelo de riesgo operativo (Pregunta 2 de MiBici Guadalajara). El objetivo central consistió en medir la estabilidad temporal de las distribuciones entre el periodo de entrenamiento basal y los datos operativos recientes, identificando desplazamientos estadísticos tempranos antes de que degraden la calidad del servicio ofrecido a los usuarios.

### Dictamen General de la Auditoría
* **Dataset Drift Global:** **0.0%** (Ninguna de las 17 variables predictoras superó el umbral crítico por defecto de $0.10$ en distancia Wasserstein o divergencia Jensen-Shannon).
* **Calidad e Integridad de Datos:** **100% de integridad** ($0$ valores nulos, $0$ registros infinitos, $0$ duplicados y adherencia estricta a los esquemas de tipos de datos `int32` y `float32`).
* **Deriva Relativa Observada:** Se identificó un gradiente claro de desplazamiento moderado concentrado en las variables de **balance neto acumulado** (`balance_rolling_12h`: $0.0711$, `balance_rolling_3h`: $0.0646$) y de **estacionalidad semanal** (`llegadas_lag_168`: $0.0527$).
* **Recomendación Operativa:** Aunque el dataset global no requiere un cese de operaciones inmediato, la deriva localizada en variables de inercia temporal justifica la necesidad de generar una **Versión 2 (Challenger)** y contrastarla empíricamente mediante un ejercicio riguroso de **A/B Testing**.

---

## 2. Definición Metodológica de Conjuntos de Datos y Justificación

Para garantizar rigor analítico y validez ecológica en la simulación de producción, los conjuntos se definieron siguiendo la partición temporal estricta anti-fuga (*anti-leakage*) del proyecto:

| Conjunto | Periodo Temporal | Registros Muestreados | Justificación Metodológica y Operativa |
| :--- | :--- | :---: | :--- |
| **Referencia (Baseline)** | `timestamp < 2025-12-31 22:00:00` (Año 2025) | 7,500 | Representa el régimen operativo anual bajo el cual se entrenó y optimizó la versión actual de producción (**Versión 1 Champion: `lgbm_profundo`**). Captura un ciclo estacional completo de primavera, verano, otoño e invierno. |
| **Actual (Producción)** | `timestamp >= 2026-01-01 00:00:00` (Año 2026) | 7,500 | Representa el flujo de datos no vistos en producción durante el siguiente ciclo anual (2026). Permite simular el comportamiento del sistema ante cambios de hábitos urbanos, clima y demanda real en un nuevo año. |

> **Nota de Muestreo:** Se aplicó un muestreo reproducible balanceado con semilla fija (`seed=42`) sobre las particiones resultantes tras excluir las ventanas de calentamiento (*warm-up*) y las dos últimas horas de entrenamiento para prevenir fuga temporal hacia el conjunto de prueba.

---

## 3. Métricas de Calidad de Datos (Data Quality)

La suite `DataSummaryPreset` de Evidently confirmó la óptima higiene de los datos en ambas ventanas temporales:
* **Valores Faltantes (*Missing Values*):** $0.0\%$ tanto en referencia como en el conjunto actual para las 17 características.
* **Integridad de Tipos:** Todas las variables numéricas se conservan en rango acotado sin desbordamientos de `float32` ni valores no finitos (`NaN`, `Inf`).
* **Consistencia de Infraestructura:** La variable `capacity` mantiene consistencia perfecta con el catálogo oficial de estaciones de MiBici Guadalajara (valores enteros positivos entre 10 y 48 anclajes físicos).

---

## 4. Ranking de Deriva Estadística por Variable

La tabla a continuación resume las 17 variables predictoras evaluadas con `DataDriftPreset`, ordenadas de mayor a menor distancia estadística:

| Variable | Prueba Estadística Aplicada | Distancia Obtenida | Umbral Alerta | Umbral Crítico | Estado de Deriva |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `balance_rolling_12h` | Wasserstein Normalizada | **0.0711** | 0.05 | 0.10 | 🟡 Deriva Moderada |
| `balance_rolling_3h` | Wasserstein Normalizada | **0.0646** | 0.05 | 0.10 | 🟡 Deriva Moderada |
| `llegadas_lag_168` | Wasserstein Normalizada | **0.0527** | 0.05 | 0.10 | 🟡 Deriva Moderada |
| `llegadas_lag_1` | Wasserstein Normalizada | 0.0406 | 0.05 | 0.10 | 🟢 Estable |
| `salidas_lag_168` | Wasserstein Normalizada | 0.0391 | 0.05 | 0.10 | 🟢 Estable |
| `latitude` | Wasserstein Normalizada | 0.0330 | 0.05 | 0.10 | 🟢 Estable |
| `salidas_lag_1` | Wasserstein Normalizada | 0.0263 | 0.05 | 0.10 | 🟢 Estable |
| `llegadas_lag_2` | Wasserstein Normalizada | 0.0250 | 0.05 | 0.10 | 🟢 Estable |
| `salidas_lag_2` | Wasserstein Normalizada | 0.0201 | 0.05 | 0.10 | 🟢 Estable |
| `llegadas_lag_24` | Wasserstein Normalizada | 0.0201 | 0.05 | 0.10 | 🟢 Estable |
| `salidas_lag_24` | Wasserstein Normalizada | 0.0154 | 0.05 | 0.10 | 🟢 Estable |
| `longitude` | Wasserstein Normalizada | 0.0147 | 0.05 | 0.10 | 🟢 Estable |
| `capacity` | Jensen-Shannon Distance | 0.0132 | 0.05 | 0.10 | 🟢 Estable |
| `sin_hour` | Wasserstein Normalizada | 0.0130 | 0.05 | 0.10 | 🟢 Estable |
| `cos_hour` | Wasserstein Normalizada | 0.0124 | 0.05 | 0.10 | 🟢 Estable |
| `sin_dow` | Wasserstein Normalizada | 0.0088 | 0.05 | 0.10 | 🟢 Estable |
| `cos_dow` | Jensen-Shannon Distance | 0.0037 | 0.05 | 0.10 | 🟢 Estable |

---

## 5. Análisis e Interpretación por Familias de Variables

### A. Variables de Inercia y Balance Neto Móvil (`balance_rolling_12h` y `balance_rolling_3h`)
* **Comportamiento Observado:** Son las dos variables con mayor desplazamiento relativo del sistema ($0.0711$ y $0.0646$). El balance rodante mide el diferencial neto entre llegadas y salidas en ventanas de 3 y 12 horas.
* **Causa Raíz:** A inicios de 2026, la reactivación de actividades académicas y laborales en la Zona Metropolitana de Guadalajara generó patrones asimétricos más marcados entre estaciones atractores (centros corporativos y universitarios) y estaciones emisoras (zonas habitacionales). Esto aumentó la dispersión y las colas de la distribución de balance neto acumulado.
* **Riesgo:** Estas características son los predictores primarios para anticipar vaciado y llenado; un sesgo en su media puede descalibrar el cálculo de umbrales internos de decisión del árbol.

### B. Lags Semanales (`llegadas_lag_168` y `salidas_lag_168`)
* **Comportamiento Observado:** Deriva de $0.0527$ en llegadas y $0.0391$ en salidas.
* **Causa Raíz:** El desfase del calendario litúrgico y de festividades de fin de año e inicio de ciclo lectivo (enero-febrero 2026) genera ligeras divergencias respecto a la semana equivalente de 2025.

### C. Lags Horarios e Inmediatos (`lag_1`, `lag_2`, `lag_24`)
* **Comportamiento Observado:** Variaciones muy controladas ($<0.041$). La microdinámica de corto plazo de una estación conserva regularidad en relación con su estado horario previo.

### D. Infraestructura y Coordenadas Geográficas
* **Comportamiento Observado:** Invarianza casi total (`capacity`: $0.0132$, `latitude`: $0.0330$, `longitude`: $0.0147$). Esto confirma que la red física de estaciones de MiBici no sufrió reconfiguraciones drásticas ni expansiones no documentadas entre 2025 y 2026.

---

## 6. Implicaciones para el Desempeño del Modelo P2

El modelo P2 predice el riesgo multiclase en un horizonte de 2 horas hacia adelante:
* **Clase 0 (Normal):** La estación conserva disponibilidad operativa ($85\%-90\%$ de los periodos).
* **Clase 1 (Desabasto):** Riesgo inminente de quedarse vacía a 2 horas (crítica para el usuario que necesita tomar una bicicleta).
* **Clase 2 (Saturación):** Riesgo inminente de llenarse a 2 horas (crítica para el usuario que llega a devolverla).

### Impacto Operativo del Drift Detectado:
1. **Sensibilidad al Desabasto (Recall en Clase 1):** Dado que `balance_rolling_12h` experimenta desplazamiento hacia valores negativos más extremos en horas pico vespertinas, el modelo `lgbm_profundo` (v1) podría experimentar un aumento en falsos negativos (no anticipar vaciados rápidos) o falsas alarmas si los cortes de árbol entrenados en 2025 quedaron fijos.
2. **Calibración de Probabilidades:** Las probabilidades predichas por el estimador de ensamble pueden sufrir descalibración (*overconfidence* o *underconfidence*), lo cual afecta directamente a los operadores del Centro de Control de Operaciones (CCO) que planifican el rebalanceo de furgonetas.
3. **Decisión Técnica:** Es mandatorio evaluar si un modelo alternativo con mejor regularización y pesos adaptativos (Challenger) mantiene mayor robustez ante estas variaciones temporales en 2026.

---

## 7. Evidencia Visual Generada

Para el reporte oficial se generaron y guardaron los siguientes artefactos gráficos en `reports/figures/`:
1. `evidently_drift_wasserstein_ranking.png`: Gráfico horizontal de barras con el ranking completo de deriva y líneas de umbral.
2. `evidently_distributions_drift.png`: Curvas de densidad comparativas de las 4 variables clave (2025 vs. 2026).
3. `evidently_drift_summary_card.png`: Tarjeta ejecutiva con el estado general y métricas de calidad.
4. Reportes interactivos originales disponibles en:
   * `reports/evidently/p2_data_drift.html`
   * `reports/evidently/p2_data_drift.json`
   * `reports/evidently/p2_data_drift_summary.json`
