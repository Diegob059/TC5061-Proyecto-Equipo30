# TECNOLÓGICO DE MONTERREY
## Maestría en Inteligencia Artificial Aplicada
### TC5061 — Operaciones de Inteligencia Artificial (MLOps)
**Entregable 8: Monitoreo y Reporte de Drift en el Proyecto & A/B Testing**

---

# Reporte Técnico y Ejecutivo: Monitoreo de Data Drift con Evidently y Evaluación A/B de Versiones en MLflow

## Metadatos del Proyecto

| Campo | Valor |
| :--- | :--- |
| **Proyecto / Sistema:** | Plataforma MLOps MiBici Guadalajara (Modelo P2: Riesgo Operativo a 2 Horas) |
| **Repositorio Oficial GitHub:** | [https://github.com/Diegob059/TC5061-Proyecto-Equipo30](https://github.com/Diegob059/TC5061-Proyecto-Equipo30) |
| **Modelos Evaluados:** | `mibici-equipo30-p2-riesgo` | Versión 1 (`@champion`) vs. Versión 2 (`@challenger`) |
| **Fecha de Entrega:** | 15 de Noviembre de 2026 — Equipo 30 |

## 1. Integrantes del Equipo (Equipo 30)

| Nombre del Integrante | Matrícula | Contribución en la Entrega 8 |
| :--- | :--- | :--- |
| **Ricardo Bahamón** | A01840023 | MLOps Lead: Model Registry v2, pipeline A/B testing, contrastes estadísticos y reporte |
| **Diego Becerril** | A01748115 | Lead Data Scientist: Configuración de Evidently AI, análisis de data drift y visualizaciones |
| **Gregorio Escobedo Straffon** | A01840612 | Data Engineer: Muestreo estratificado de producción 2026, validación de esquemas y tests |
| **Freddin Alcántara** | A01797741 | Product & Operations Lead: Criterios operativos CCO, formulación de umbrales y gobernanza CT |

---

## 1. Metodología y Definición de Conjuntos de Datos

En sistemas de aprendizaje automático en producción, el desempeño no es estático: la dinámica de movilidad urbana y las variaciones temporales introducen perturbaciones en las distribuciones de entrada (*data drift*) y en las relaciones funcionales (*concept drift*). En este entregable, el Equipo 30 dota a la plataforma MiBici de capacidades de observabilidad continua y experimentación controlada. Evaluamos el modelo multiclase de riesgo operativo a 2 horas (**Pregunta 2**: `0: Normal`, `1: Desabasto`, `2: Saturación`).

Para garantizar validez ecológica y reproducibilidad estricta sin fuga temporal (*anti-leakage*), se definieron dos ventanas basadas en los [datos abiertos de MiBici](https://mibici.net/es/datos-abiertos/):

* **Conjunto de Referencia (Baseline 2025):** Registros horarios desde `2025-01-01` hasta `2025-12-31 22:00:00` (4,037,300 filas totales). Representa el régimen operativo basal bajo el cual se entrenó la versión actual de producción (**Versión 1 Champion: `lgbm_profundo`**). Para la auditoría de drift se utilizó una muestra estratificada representativa de 7,500 observaciones.
* **Conjunto Actual (Producción 2026):** Registros horarios desde `2026-01-01 00:00:00` hasta `2026-09-30` (3,078,500 filas totales). Representa el comportamiento real del sistema en un ciclo anual posterior no visto durante el entrenamiento. Se utilizaron 7,500 observaciones para drift y 50,000 para el A/B testing.

---

## 2. Monitoreo y Auditoría de Data Drift con Evidently AI

Se implementó el pipeline de monitoreo continuo utilizando la versión actual de Evidently AI (`evidently==0.7.23`). Se ejecutaron simultáneamente `DataDriftPreset` y `DataSummaryPreset` sobre las **17 variables predictoras**. Se aplicó la distancia Wasserstein normalizada para variables continuas y la divergencia Jensen-Shannon para variables discretas, con un umbral crítico de $0.10$ y un umbral de advertencia temprana de $0.05$.

![Auditoría Ejecutiva de Data Drift y Calidad de Datos (Evidently)](reports/figures/evidently_drift_summary_card.png){width=48%}

![Ranking de Deriva Estadística por Variable en P2](reports/figures/evidently_drift_wasserstein_ranking.png){width=48%}

---

## 3. Interpretación Técnica de Variables y Consecuencias de Negocio

El dictamen global de Evidently confirma **0.0% de dataset drift crítico** (0 de 17 variables superaron el umbral de 0.10) y **100% de calidad de datos** (cero valores nulos, infinitos o fuera de esquema). No obstante, el ranking revela un gradiente de deriva concentrado en variables dinámicas:

1. **Balance Rodante de 12h y 3h (`balance_rolling_12h`: 0.0711, `balance_rolling_3h`: 0.0646):** Son las variables con mayor desplazamiento relativo del sistema. Miden el diferencial neto acumulado de bicicletas (llegadas menos salidas). A inicios de 2026, la reactivación laboral y académica intensificó la asimetría de viajes entre zonas residenciales y corredores corporativos/universitarios, ensanchando las colas de la distribución empírica.
2. **Lags Semanales (`llegadas_lag_168`: 0.0527, `salidas_lag_168`: 0.0391):** Reflejan ligeras divergencias por el calendario de festividades y retorno escolar de inicio de año respecto a 2025.
3. **Invarianza Física y Geográfica:** La capacidad instalada (`capacity`: 0.013) y coordenadas (`latitude`: 0.033, `longitude`: 0.015) permanecen prácticamente invariantes, certificando que la topología de estaciones no sufrió reconfiguraciones drásticas.

**Implicaciones Operativas:** En el Centro de Control de Operaciones (CCO), un sesgo en los balances acumulados puede inducir descalibración en los umbrales de probabilidad del estimador, aumentando los falsos negativos en desabasto. Esto justificó diseñar una versión alternativa con regularización reforzada.

![Comparación de Densidades Empíricas (KDE) entre 2025 y 2026](reports/figures/evidently_distributions_drift.png){width=48%}

---

## 4. Versión Alternativa (Challenger) y Resultados del A/B Testing

Ante la deriva observada, se diseñó y entrenó la **Versión 2 (Challenger: `lgbm_challenger_v2`)** incorporando: regularización L1/L2 (`reg_alpha=0.1`, `reg_lambda=0.5`), submuestreo de características (`colsample_bytree=0.80`) para evitar la dependencia excesiva de los balances rodantes, bagging (`subsample=0.85`) y menor profundidad (`depth=7`, `leaves=40`). Esta versión se registró formalmente en el Model Registry de MLflow como Versión 2 con el alias `@challenger`, manteniendo la Versión 1 como `@champion`.

Ambas versiones se evaluaron sobre 50,000 registros estratificados de producción 2026:

| Métrica Operativa Clave | Versión 1 (@champion) | Versión 2 (@challenger) | Delta Absoluto | Delta % |
| :--- | :---: | :---: | :---: | :---: |
| **Balanced Accuracy** | 0.8796 | 0.8756 | -0.0041 | -0.46% |
| **Macro F1-Score** | 0.3704 | 0.3663 | -0.0041 | -1.11% |
| **Weighted F1-Score** | 0.9087 | 0.9045 | -0.0041 | -0.45% |
| **Recall Desabasto (Clase 1 - Crítica)** | **0.8808** | **0.8756** | **-0.0052** | **-0.59%** |
| **Precisión Desabasto (Clase 1)** | 0.0440 | 0.0425 | -0.0014 | -3.22% |
| **F2-Score Desabasto (Clase 1)** | 0.1832 | 0.1781 | -0.0051 | -2.79% |
| **Recall Saturación (Clase 2)** | 0.9121 | 0.9121 | 0.0000 | 0.00% |
| **Precisión Saturación (Clase 2)** | 0.0592 | 0.0560 | -0.0032 | -5.39% |
| **Latencia Inferencia (ms / 1k)** | **4.23 ms** | **3.50 ms** | **-0.73 ms** | **-17.30%** |

![Resultados Integrales del A/B Testing: Comparación de Métricas y Matrices de Confusión (Champion v1 vs. Challenger v2)](reports/figures/ab_test_combined_panel.png){width=48%}

**Inferencia Estadística:** La prueba de McNemar confirmó que la divergencia en errores es estadísticamente significativa ($\chi^2 = 151.73$, $p < 0.001$). El análisis bootstrap al 95% de confianza (400 réplicas) para $\Delta \text{Macro F1}$ arrojó un intervalo $[-0.0051, -0.0031]$, confirmando que el Champion v1 conserva una superioridad sistemática en balance multiclase.

---

## 5. Decisión de Versión y Recomendación de Continuous Training (CT)

**Decisión del A/B Testing:** Se determina **mantener la Versión 1 (`lgbm_profundo`) como `@champion` activo en producción**. La justificación de negocio es contundente: el Champion logra mayor Recall en Desabasto (88.08% vs. 87.56%) y mayor Macro F1 (0.3704 vs. 0.3663). En MiBici, la insatisfacción por desabasto (no poder tomar bicicleta) es el evento de mayor fricción operativa; reducir medio punto porcentual de recall a cambio de menor latencia (3.5 ms vs. 4.2 ms) sería perjudicial para el usuario final.

**Estrategia de Continuous Training (CT) Recomendada:**
1. **Disparadores de Drift (Evidently):** Auditoría semanal programada. Si `balance_rolling_12h` excede $0.10$ o más del 25% de variables superan $0.08$, se gatilla el reentrenamiento automático.
2. **Disparadores de Desempeño:** Si el Recall en Desabasto a 14 días cae de 85.0% o el Macro F1 de 0.35, se activa reentrenamiento correctivo.
3. **Esquema de Reentrenamiento:** Ventana rodante de 12 meses con ponderación temporal decrescente, incorporando la regularización L1/L2 y `colsample_bytree=0.80` validadas en el Challenger.
4. **Gateways de Despliegue:** Ningún modelo generado por CT sustituirá al Champion sin validar cero errores de esquema, latencia < 10 ms y paridad estadística en Recall de Desabasto en un A/B test canario de 72 horas.
