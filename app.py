from __future__ import annotations

import base64
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from eeff_analyzer.catalog import FINANCIAL_STATEMENT_CATALOG, NON_MONETARY_CATALOG
from eeff_analyzer.analysis import calculate_ratios
from eeff_analyzer.historical import company_folders, entity_options, filter_by_entity, horizontal_analysis, load_local_cases, percentage_change, ratio_history, real_statement_history, statement_history, vertical_analysis
from eeff_analyzer.inflation import ANNUAL_ADJUSTMENT_FACTORS
from eeff_analyzer.quality import balance_check, historical_quality

st.set_page_config(page_title="Analizador EEFF IFRS", page_icon="📊", layout="wide")


def raw_directory_signature(directory: Path) -> tuple:
    """Firma barata de una carpeta de empresa: cambia si se agrega, quita o
    modifica un ZIP, para que el caché se invalide solo sin releer en cada clic."""
    return tuple(sorted((path.name, path.stat().st_size, path.stat().st_mtime) for path in directory.glob("*.zip")))


@st.cache_data(show_spinner="Leyendo los ZIP XBRL de data/raw…")
def load_local_cases_cached(directory_str: str, _signature: tuple):
    return load_local_cases(directory_str)


def format_number(value: object) -> str:
    """Formato exacto en pesos, con separador de miles estilo chileno."""
    if pd.isna(value):
        return "—"
    return f"{int(value):,}".replace(",", ".")


def format_millions(value: object, decimals: int = 1) -> str:
    """Formato compacto en millones, con separador de miles/decimales estilo chileno."""
    if pd.isna(value):
        return "—"
    millions = float(value) / 1_000_000
    text = f"{millions:,.{decimals}f}"
    integer_part, _, decimal_part = text.partition(".")
    integer_part = integer_part.replace(",", ".")
    formatted = f"{integer_part},{decimal_part}" if decimals > 0 else integer_part
    return f"{formatted} MM"


def format_currency(value: object, show_millions: bool) -> str:
    return format_millions(value) if show_millions else format_number(value)


def format_unit_label(unit: object) -> str:
    """Muestra la unidad de forma legible: 'iso4217:CLP' -> 'CLP'."""
    if pd.isna(unit):
        return "—"
    text = str(unit)
    return text.split(":")[-1] if ":" in text else text


def table_height(frame: pd.DataFrame) -> int:
    """Alto necesario para mostrar la tabla completa, sin scroll interno.

    Streamlit muestra unas 10 filas por defecto y corta el resto; varias tablas
    de este dashboard superan ese largo y quedarían truncadas sin avisar.
    """
    return (len(frame) + 1) * 35 + 3


def format_count(value: object) -> str:
    """Formato para conteos sin unidad monetaria (por ejemplo, número de acciones)."""
    if pd.isna(value):
        return "—"
    return f"{int(value):,}".replace(",", ".")


def format_ratio_value(value: object, unit: str, show_millions: bool) -> str:
    """Formatea un valor según su unidad declarada: %, veces, días, por acción o monto."""
    if pd.isna(value):
        return "—"
    if unit == "%":
        return f"{float(value):.1f}%"
    if unit == "Veces":
        return f"{float(value):.2f}x"
    if unit == "Días":
        return f"{float(value):.1f} días"
    if unit == "$/acción":
        # Los montos por acción son cifras pequeñas: nunca se llevan a millones.
        return f"${float(value):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return format_currency(value, show_millions)


_logo_path = ROOT / "Elephant.png"
_logo_b64 = base64.b64encode(_logo_path.read_bytes()).decode("ascii") if _logo_path.exists() else None

st.markdown(
    """
    <style>
    /* Encabezado compacto: acompaña a todas las hojas sin robarles espacio.
       Los datos del autor viven en la portada (hoja Inicio), no acá. */
    .analizador-header {
        background: #ffffff;
        border: 1px solid #d7e6ee;
        border-left: 6px solid #157a8a;
        border-radius: 12px;
        padding: 0.8rem 1.4rem;
        margin-bottom: 0.6rem;
        display: flex;
        align-items: center;
        gap: 1.2rem;
        box-shadow: 0 1px 6px rgba(11, 61, 98, 0.05);
    }
    .analizador-header img {
        height: 62px;
        width: auto;
    }
    .analizador-header h1 {
        color: #0b3d62;
        font-size: 1.65rem;
        font-weight: 800;
        margin: 0;
    }
    /* Portada: acá sí va la identidad completa, en grande. */
    .analizador-portada {
        background: linear-gradient(135deg, #f4fafc 0%, #ffffff 60%);
        border: 1px solid #d7e6ee;
        border-left: 6px solid #157a8a;
        border-radius: 14px;
        padding: 1.8rem 2rem;
        margin-bottom: 1.4rem;
        display: flex;
        align-items: center;
        gap: 2rem;
        box-shadow: 0 2px 10px rgba(11, 61, 98, 0.06);
    }
    .analizador-portada img {
        height: 150px;
        width: auto;
    }
    .analizador-portada .autor {
        color: #0b3d62;
        font-size: 2rem;
        font-weight: 800;
        margin: 0;
        line-height: 1.15;
    }
    .analizador-portada .credencial {
        color: #157a8a;
        font-size: 1.15rem;
        font-weight: 600;
        margin-top: 0.5rem;
    }
    .analizador-portada .lab {
        color: #3c6b82;
        font-size: 0.95rem;
        margin-top: 0.6rem;
    }
    /* Los botones de hoja ocupan el ancho completo, sin amontonarse. */
    div[role="radiogroup"] {
        gap: 1.6rem;
    }
    [data-testid="stMetricValue"] {
        white-space: normal;
        overflow: visible;
        text-overflow: unset;
        line-height: 1.25;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

_logo_html = f'<img src="data:image/png;base64,{_logo_b64}" alt="Elephant Data Labs" />' if _logo_b64 else ""
st.markdown(
    f"""
    <div class="analizador-header">
        {_logo_html}
        <h1>Analizador EEFF IFRS</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

raw_directory = ROOT / "data" / "raw"
folders = company_folders(raw_directory)

# Los botones de hoja van en su propia fila, a lo ancho de la página.
page = st.radio(
    "Hoja",
    ["Inicio", "EEFF", "Análisis", "Histórico", "Industria", "Interpretación"],
    horizontal=True,
    label_visibility="collapsed",
)

if page == "Inicio":
    st.markdown(
        f"""
        <div class="analizador-portada">
            {_logo_html}
            <div>
                <div class="autor">Carlos Alaniz Salinas</div>
                <div class="credencial">Ingeniero Civil Industrial · Magíster Data Science · Candidato a Magíster en Gestión de Inversiones Financieras</div>
                <div class="lab">Elephant Data Labs · Análisis determinístico de estados financieros IFRS desde XBRL</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Cómo cargar la información")
    st.markdown(
        "La aplicación no descarga nada de internet: lee los **ZIP XBRL** que usted deje en el "
        "repositorio local `data/raw`. Cada empresa vive en su propia carpeta."
    )

    guide_cols = st.columns(2)
    with guide_cols[0]:
        st.markdown("**1. Obtener los archivos**")
        st.markdown(
            "Descargue de la CMF el ZIP XBRL de cada cierre anual que quiera analizar. "
            "Es el mismo archivo que la empresa envía como estados financieros; no se modifica."
        )
        st.markdown("**2. Crear una carpeta por entidad**")
        st.code(
            "data/raw/\n"
            "  empresa_uno/\n"
            "    empresa_uno_2023_12_xbrl.zip\n"
            "    empresa_uno_2024_12_xbrl.zip\n"
            "    empresa_uno_2025_12_xbrl.zip\n"
            "  empresa_dos/\n"
            "    empresa_dos_2025_12_xbrl.zip",
            language="text",
        )
        st.markdown(
            "El nombre de la carpeta es el que aparece en el selector **Empresa**. "
            "El nombre real y el RUT se leen del propio XBRL, no del nombre del archivo."
        )
    with guide_cols[1]:
        st.markdown("**3. Elegir y analizar**")
        st.markdown(
            "Al abrir la aplicación se listan las carpetas sin abrir ningún ZIP. "
            "Solo se lee la carpeta que usted elija, así que agregar empresas no hace más lenta la partida."
        )
        st.markdown("**Qué se valida automáticamente**")
        st.markdown(
            "- El RUT se toma de cada archivo: si una carpeta mezcla dos entidades, se avisa y no se combinan.\n"
            "- No se aceptan dos archivos de la misma entidad con el mismo cierre.\n"
            "- Se controla que Activos = Pasivos + Patrimonio en cada cierre.\n"
            "- **Histórico** necesita al menos dos cierres de la misma entidad."
        )
        st.markdown("**Sobre las cifras**")
        st.markdown(
            "Los montos se muestran en millones (se puede desactivar) y, en Histórico, "
            "también corregidos por inflación a pesos del último período, con el IPC anual del INE "
            "(diciembre a diciembre). Las razones y los conteos no se corrigen."
        )

    st.markdown("### Estado actual del repositorio")
    if folders:
        inventory = pd.DataFrame([
            {
                "Carpeta": folder["label"],
                "Archivos ZIP": len(list(Path(folder["path"]).glob("*.zip"))),
                "Ubicación": str(Path(folder["path"]).relative_to(ROOT)).replace("\\", "/"),
            }
            for folder in folders
        ])
        st.dataframe(inventory, use_container_width=True, hide_index=True, height=table_height(inventory))
        st.caption(
            "Conteo por nombre de archivo: no se abre ningún ZIP hasta que usted elige una empresa "
            "en las hojas de análisis."
        )
    else:
        st.warning(
            "Todavía no hay ZIP en `data/raw`. Cree una carpeta por empresa (por ejemplo `data/raw/empresa_uno`) "
            "y deje ahí sus archivos ZIP para empezar."
        )

    st.markdown("### Qué hay en cada hoja")
    st.markdown(
        "- **EEFF** — estados financieros de un cierre, con la trazabilidad al concepto XBRL de cada cuenta.\n"
        "- **Análisis** — indicadores de ese mismo cierre, con su fórmula y su interpretación.\n"
        "- **Histórico** — evolución entre cierres: cifras nominales y ajustadas por IPC, ratios, "
        "grados de apalancamiento y análisis vertical y horizontal.\n"
        "- **Industria** e **Interpretación** — módulos en preparación."
    )
    st.markdown(
        "**Por qué se trabaja desde el XBRL** — es el mismo archivo que la empresa presenta al regulador, "
        "así que cada cifra del tablero puede rastrearse hasta su concepto en el estado financiero original."
    )
    st.stop()

# Las columnas se crean primero y se rellenan por partes: entre medio hay que
# leer la carpeta elegida, porque los cierres disponibles dependen de ella.
control_cols = st.columns([1.6, 1.1, 1])
with control_cols[0]:
    if folders:
        folder_labels = [folder["label"] for folder in folders]
        selected_folder_label = st.selectbox(
            "Empresa (carpeta en data/raw)",
            folder_labels,
            help="Cada carpeta dentro de data/raw es una empresa. Solo se lee la carpeta elegida, no todo el repositorio.",
        )
        selected_folder = folders[folder_labels.index(selected_folder_label)]
    else:
        selected_folder = None
        st.selectbox("Empresa (carpeta en data/raw)", ["Sin ZIP en data/raw"], disabled=True)

if selected_folder is None:
    st.error(
        "No hay ZIP XBRL en data/raw. Cree una carpeta por empresa dentro de data/raw "
        "(por ejemplo data/raw/empresa_uno) y deje ahí sus archivos ZIP."
    )
    st.stop()

try:
    all_cases = load_local_cases_cached(
        str(selected_folder["path"]),
        raw_directory_signature(selected_folder["path"]),
    )
except Exception as exc:
    st.error(f"No fue posible leer los ZIP XBRL de «{selected_folder['label']}»: {exc}")
    st.stop()

company_options = entity_options(all_cases)
if not company_options:
    st.error(
        f"Los ZIP de «{selected_folder['label']}» no declaran un RUT identificable en el XBRL, "
        "así que no se pueden asociar con seguridad a una empresa."
    )
    st.stop()

if len(company_options) == 1:
    selected_company = company_options[0]
else:
    # Caso anormal: una carpeta debería contener una sola empresa. No se elige
    # por el usuario de forma silenciosa; se avisa y se pide confirmación.
    st.warning(
        f"La carpeta «{selected_folder['label']}» contiene ZIP de {len(company_options)} entidades distintas. "
        "Elija cuál analizar; no se mezclan entre sí."
    )
    entity_labels = [
        f"{option['display_name'] or 'Sin nombre'} (RUT {option['entity_identifier']})"
        for option in company_options
    ]
    picked_entity = st.selectbox("Entidad dentro de la carpeta", entity_labels)
    selected_company = company_options[entity_labels.index(picked_entity)]

with control_cols[1]:
    case_labels = [case.closing_date for case in selected_company["cases"]]
    selected_case_label = st.selectbox("Cierre a cargar", case_labels, index=len(case_labels) - 1)
    selected_case = selected_company["cases"][case_labels.index(selected_case_label)]
with control_cols[2]:
    show_millions = st.toggle(
        "Mostrar cifras en millones",
        value=True,
        help="Los montos en pesos se redondean a millones para lectura rápida. Las cifras exactas siguen disponibles en el detalle de hechos XBRL y en las tablas de trazabilidad.",
    )

instance = selected_case.instance
periods = instance.periods()
selected_period = max(periods)

st.divider()

if page == "EEFF":
    st.subheader(f"EEFF / XBRL — cierre {selected_period}")
    st.write("Las cuentas se seleccionan por concepto XBRL y por contexto sin dimensiones cuando está disponible.")
    entity = next(iter(instance.entity_identifiers()), "Entidad no identificada")
    entity_display = instance.entity_name() or entity
    check = balance_check(instance, selected_period)
    quality_columns = st.columns([1.6, 1, 1.3, 1])
    quality_columns[0].metric("Entidad XBRL", entity_display, help=f"RUT: {entity}" if entity_display != entity else None)
    quality_columns[1].metric("Activos", format_currency(check["Activos"], show_millions))
    quality_columns[2].metric("Pasivos + patrimonio", format_currency(check["Pasivos + patrimonio"], show_millions))
    quality_columns[3].metric("Diferencia contable", format_number(check["Diferencia"]))
    if check["Estado"] == "Validado":
        st.success("Ecuación contable validada: Activos = Pasivos + Patrimonio.")
    else:
        st.warning(f"Control de ecuación contable: {check['Estado']}.")
    table = instance.statement_rows(FINANCIAL_STATEMENT_CATALOG, selected_period)
    declared_units = sorted({format_unit_label(unit) for unit in table["Unidad"].dropna().unique()})
    scale_note = "en millones" if show_millions else "cifras exactas"
    units_text = ", ".join(declared_units) if declared_units else "unidad no informada"
    st.caption(f"Montos {scale_note}, según la unidad declarada en el XBRL: {units_text}.")

    for statement_name in table["Estado"].drop_duplicates().tolist():
        group = table[table["Estado"] == statement_name]
        st.markdown(f"**{statement_name}**")
        clean = pd.DataFrame({
            "Cuenta": group["Cuenta"].values,
            "Valor": [format_currency(value, show_millions) for value in group["Valor"]],
        })
        st.dataframe(clean, use_container_width=True, hide_index=True, height=table_height(clean))
        with st.expander(f"Trazabilidad XBRL — {statement_name}"):
            detail = pd.DataFrame({
                "Cuenta": group["Cuenta"].values,
                "Concepto XBRL": group["Concepto XBRL"].values,
                "Contexto": group["Contexto"].values,
            })
            st.dataframe(detail, use_container_width=True, hide_index=True)
    st.caption("La diferencia contable del control de ecuación (arriba) siempre se muestra exacta, en pesos.")

    shares_table = instance.statement_rows(NON_MONETARY_CATALOG, selected_period)
    if not shares_table["Valor"].isna().all():
        st.markdown("**Acciones**")
        shares_clean = pd.DataFrame({
            "Concepto": shares_table["Cuenta"].values,
            "Cantidad": [format_count(value) for value in shares_table["Valor"]],
        })
        st.dataframe(shares_clean, use_container_width=True, hide_index=True)
        st.caption("El número de acciones no es un monto en pesos: no se expresa en millones ni se corrige por inflación.")

    with st.expander("Explorar todos los hechos extraídos"):
        facts = instance.facts_frame(selected_period)
        st.dataframe(facts, use_container_width=True, hide_index=True)

elif page == "Análisis":
    st.subheader(f"Análisis — cierre {selected_period}")
    st.write("Indicadores calculados solo desde hechos XBRL del cierre seleccionado. No hay estimaciones ni IA.")
    ratios = calculate_ratios(instance, selected_period)
    calculated = ratios[ratios["Estado"] == "Calculado"].copy()

    metric_values = {row["Indicador"]: row for _, row in calculated.iterrows()}
    columns = st.columns(4)
    featured = ["Liquidez corriente", "Capital de trabajo", "Endeudamiento sobre activos", "ROE al cierre"]
    for column, name in zip(columns, featured):
        row = metric_values.get(name)
        with column:
            if row is None:
                st.metric(name, "—")
            else:
                st.metric(name, format_ratio_value(row["Valor"], row["Unidad"], show_millions))

    display = ratios[["Indicador", "Valor", "Unidad", "Fórmula", "Estado"]].copy()
    display["Valor"] = ratios.apply(lambda row: format_ratio_value(row["Valor"], row["Unidad"], show_millions), axis=1)
    display["Unidad"] = display["Unidad"].map(format_unit_label)
    # Altura calculada para mostrar todos los indicadores sin scroll interno:
    # con el alto por defecto la tabla corta las últimas filas.
    st.dataframe(display, use_container_width=True, hide_index=True, height=table_height(display))
    st.subheader("Du Pont")
    dupont = ratios[ratios["Indicador"].isin(["Margen neto", "Rotación de activos al cierre", "Multiplicador patrimonial", "ROE Du Pont al cierre"])].copy()
    dupont["Valor"] = dupont.apply(lambda row: format_ratio_value(row["Valor"], row["Unidad"], show_millions), axis=1)
    st.dataframe(dupont[["Indicador", "Valor", "Fórmula", "Estado"]], use_container_width=True, hide_index=True)
    with st.expander("¿Qué significa cada indicador?"):
        for _, row in ratios.iterrows():
            if row["Interpretación"]:
                st.markdown(f"**{row['Indicador']}** — {row['Interpretación']}")
    with st.expander("Trazabilidad XBRL de los ratios"):
        st.dataframe(ratios[["Indicador", "Numerador XBRL", "Denominador XBRL", "Estado"]], use_container_width=True, hide_index=True)
    st.caption("ROA, ROE y la rotación de activos usan saldos al cierre. La hoja Histórico permite calcularlos también con promedios entre períodos.")
elif page == "Histórico":
    st.subheader("Histórico")
    selected_entity = selected_company["entity_identifier"]
    cases, other = filter_by_entity(all_cases, selected_entity)
    unidentified = [case for case in other if not case.entity_identifier]
    if unidentified:
        unidentified_text = ", ".join(case.path.name for case in unidentified)
        st.warning(f"Hay ZIP sin RUT identificable en esta carpeta; no se pueden asociar a ninguna empresa: {unidentified_text}")
    other_companies = len(other) - len(unidentified)
    if other_companies:
        st.caption(f"La carpeta contiene además {other_companies} cierre(s) de otras entidades; no se mezclan con esta serie.")
    if len(cases) < 2:
        st.info(f"Deje al menos dos ZIP XBRL de la misma entidad en la carpeta «{selected_folder['label']}» para construir la evolución.")
        st.stop()

    periods_hist = [case.closing_date for case in cases]
    entity = selected_entity or cases[0].entity_identifier or "Entidad no identificada"
    entity_display = next((case.entity_name for case in reversed(cases) if case.entity_name), None) or entity
    st.caption(f"{len(cases)} cierres locales: {periods_hist[0]} a {periods_hist[-1]} · Entidad XBRL: {entity_display}")
    expected_years = set(range(int(periods_hist[0][:4]), int(periods_hist[-1][:4]) + 1))
    actual_years = {int(period[:4]) for period in periods_hist}
    missing_years = sorted(expected_years - actual_years)
    if missing_years:
        st.warning(f"La serie tiene años sin datos validados: {', '.join(map(str, missing_years))}. Los ratios con saldos promedio no se calculan a través de ese vacío.")

    st.markdown("#### Cifras principales")
    amounts = statement_history(cases, FINANCIAL_STATEMENT_CATALOG)
    amounts_display = amounts.copy()
    for period in periods_hist:
        amounts_display[period] = amounts_display[period].map(lambda value: format_currency(value, show_millions))
    st.dataframe(amounts_display, use_container_width=True, hide_index=True, height=table_height(amounts_display))
    st.caption("Cifras nominales, en millones de la unidad declarada." if show_millions else "Cifras nominales exactas, en la unidad declarada.")

    st.markdown("#### Cifras principales ajustadas por IPC")
    base_year = int(periods_hist[-1][:4])
    real_amounts = real_statement_history(amounts, cases, base_year)
    missing_factor_periods = [period for period in periods_hist if real_amounts[period].isna().all()]
    if missing_factor_periods:
        st.warning(
            "Falta el factor de IPC para llevar estos cierres a pesos de "
            f"{periods_hist[-1]}: {', '.join(missing_factor_periods)}. Actualice la tabla en "
            "eeff_analyzer/inflation.py con el IPC de diciembre que publique el INE."
        )
    real_display = real_amounts.copy()
    for period in periods_hist:
        real_display[period] = real_display[period].map(lambda value: format_currency(value, show_millions))
    st.caption(
        f"Montos nominales llevados a pesos de {periods_hist[-1]} usando la variación anual del "
        "IPC (INE, diciembre a diciembre)."
    )
    st.dataframe(real_display, use_container_width=True, hide_index=True, height=table_height(real_display))

    account_options = amounts["Cuenta"].tolist()
    chart_account = st.selectbox("Cuenta para comparar nominal vs. ajustado por IPC", account_options)
    nominal_row = amounts.loc[amounts["Cuenta"] == chart_account].iloc[0]
    real_row = real_amounts.loc[real_amounts["Cuenta"] == chart_account].iloc[0]
    comparison = pd.DataFrame(
        {
            "Nominal": [float(nominal_row[period]) if pd.notna(nominal_row[period]) else None for period in periods_hist],
            f"Real (pesos {periods_hist[-1]})": [float(real_row[period]) if pd.notna(real_row[period]) else None for period in periods_hist],
        },
        index=periods_hist,
    )
    st.line_chart(comparison)

    with st.expander("Fuente del ajuste por IPC"):
        factors_table = pd.DataFrame(
            [
                {"Año": year, "Variación IPC dic-dic": f"{(float(factor) - 1) * 100:.1f}%", "Factor": f"{float(factor):.3f}"}
                for year, factor in sorted(ANNUAL_ADJUSTMENT_FACTORS.items())
            ]
        )
        st.dataframe(factors_table, use_container_width=True, hide_index=True)
        st.caption(
            "Fuente: Instituto Nacional de Estadísticas (INE), variación del Índice de Precios al "
            "Consumidor medida de diciembre a diciembre. Tabla de mantención manual: agregar la fila "
            "del año siguiente cuando el INE publique el IPC de diciembre (primeros días de enero)."
        )

    st.markdown("#### Evolución de ratios")
    ratios = ratio_history(cases)
    # Solo se ofrecen para el gráfico los indicadores en % o veces: son comparables
    # en una misma escala. "Capital de trabajo" está en pesos y, mezclado con ellos,
    # aplasta el gráfico (queda todo lo demás en una línea plana); se sigue viendo,
    # con su propia escala, en la tabla de abajo.
    chartable_ratios = ratios[ratios["Unidad"].isin(["%", "Veces", "Días"])]
    ratio_names = chartable_ratios["Indicador"].tolist()
    selected_indicators = st.multiselect(
        "Indicadores para el gráfico",
        ratio_names,
        default=[name for name in ["Liquidez corriente", "Endeudamiento sobre activos", "Margen neto", "ROE al cierre"] if name in ratio_names],
        help="Solo indicadores en % o veces: son los que se pueden comparar en un mismo gráfico. El capital de trabajo (en pesos) se excluye por escala; está en la tabla de abajo.",
    )
    if selected_indicators:
        chart = ratios[ratios["Indicador"].isin(selected_indicators)].set_index("Indicador")[periods_hist].T
        # Los valores vienen como Decimal (aritmética exacta): hay que convertirlos a
        # float antes de graficar, si no Altair no logra inferir una escala numérica
        # y el gráfico se renderiza colapsado (sin líneas visibles).
        chart = chart.apply(pd.to_numeric, errors="coerce")
        st.line_chart(chart)
    ratios_display = ratios[["Indicador", "Unidad", "Fórmula"] + periods_hist].copy()
    for _, row in ratios.iterrows():
        for period in periods_hist:
            ratios_display.loc[row.name, period] = format_ratio_value(row[period], row["Unidad"], show_millions)
    ratios_display["Unidad"] = ratios_display["Unidad"].map(format_unit_label)
    st.dataframe(ratios_display, use_container_width=True, hide_index=True, height=table_height(ratios_display))
    with st.expander("¿Qué significa cada indicador?"):
        for _, row in ratios.iterrows():
            if row["Interpretación"]:
                st.markdown(f"**{row['Indicador']}** — {row['Interpretación']}")

    st.markdown("#### Variación interanual de las cuentas")
    changes = percentage_change(amounts, periods_hist)
    change_columns = [column for column in changes.columns if " vs " in column]
    for column in change_columns:
        changes[column] = changes[column].map(lambda value: "—" if pd.isna(value) else f"{value:.1f}%")
    st.dataframe(changes, use_container_width=True, hide_index=True, height=table_height(changes))
    st.caption("La tabla de ratios incluye indicadores al cierre y, desde el segundo período disponible, versiones con saldos promedio y los grados de apalancamiento (que requieren dos años para calcularse).")

    st.markdown("#### Análisis vertical")
    st.caption("Cada partida como porcentaje de su base del mismo período: las cuentas de balance sobre activos totales y las de resultados sobre ingresos.")
    vertical = vertical_analysis(amounts, periods_hist)
    vertical_display = vertical[["Estado", "Cuenta"]].copy()
    for period in periods_hist:
        vertical_display[period] = vertical[period].map(lambda value: "—" if pd.isna(value) else f"{float(value):.1f}%")
    st.dataframe(vertical_display, use_container_width=True, hide_index=True, height=table_height(vertical_display))

    st.markdown("#### Análisis horizontal")
    st.caption(f"Números índice con base 100 en {periods_hist[0]}. Un índice de 130 indica un nivel 30% superior al del año base.")
    horizontal = horizontal_analysis(amounts, periods_hist)
    horizontal_display = horizontal[["Estado", "Cuenta"]].copy()
    for period in periods_hist:
        horizontal_display[period] = horizontal[period].map(lambda value: "—" if pd.isna(value) else f"{float(value):.0f}")
    st.dataframe(horizontal_display, use_container_width=True, hide_index=True, height=table_height(horizontal_display))
    st.caption("Ambos análisis usan cifras nominales, tal como vienen del XBRL; el efecto de la inflación se aísla en la tabla ajustada por IPC de más arriba.")

    with st.expander("Trazabilidad y controles de los ZIP locales"):
        quality = historical_quality(all_cases, selected_entity)
        quality["Diferencia"] = quality["Diferencia"].map(format_number)
        st.dataframe(quality, use_container_width=True, hide_index=True)
elif page == "Industria":
    st.subheader("Industria")
    st.info("Siguiente módulo: comparar con pares seleccionados; no se incorpora aún descarga ni base externa.")
else:
    st.subheader("Interpretación")
    st.info("Punto reservado para una API de IA intercambiable. Recibirá ratios calculados y datos validados, nunca el control del proceso.")
