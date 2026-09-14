"""
Asistente Inteligente NBUS
TFM - Master en Data Science, Business Analytics y Big Data

Para ejecutar:
    streamlit run app_nbus.py

Antes de ejecutar, crea un archivo .env en la misma carpeta con:
    OPENAI_API_KEY=tu-clave-aqui

Estructura de carpeta esperada:
    app_nbus.py
    .env
    .streamlit/
        config.toml          <- activa el servido de imágenes estáticas (incluido)
    resumen_por_ruta.csv
    cobertura_municipios.csv
    output_clusters.csv
    paradas_enriquecidas.csv
    static/
        logo_nbus.png        <- logo NBUS para la cabecera
        bus_nbus.png         <- foto del autobús para la barra lateral

Nota de rendimiento: el logo y la foto se sirven como ficheros estáticos
(en vez de incrustarlos en base64 dentro del HTML) para que el navegador
los cachee y no se vuelvan a transmitir en cada interacción. Por el mismo
motivo, la librería langchain_openai se importa de forma diferida (solo
cuando se hace la primera pregunta), para que la página inicial no tenga
que esperar a esa importación pesada.
"""

import os
import io
import contextlib
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# ──────────────────────────────────────────────────────────
# CONFIGURACIÓN INICIAL
# ──────────────────────────────────────────────────────────
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

st.set_page_config(
    page_title="Asistente NBUS",
    page_icon="🚌",
    layout="wide"
)

# ──────────────────────────────────────────────────────────
# IDENTIDAD CORPORATIVA NBUS
# Colores extraídos directamente del logo oficial:
#   rojo NBUS  -> #DA291C
#   tinta NBUS -> #211915 (negro cálido, no negro puro)
# ──────────────────────────────────────────────────────────
RED = "#DA291C"
RED_HOVER = "#B22116"
RED_TINT = "#FAE5E3"
DARK = "#211915"
DARK_BORDER = "#423B38"
BG = "#F7F5F4"
GRAY_TEXT = "#6B6360"
LINE = "#E3DAD8"

# Rutas estáticas (requieren server.enableStaticServing=true en .streamlit/config.toml)
LOGO_SRC = "app/static/logo_nbus.png"
BUS_SRC = "app/static/bus_nbus.png"
bus_disponible = (STATIC_DIR / "bus_nbus.png").exists()

# ──────────────────────────────────────────────────────────
# ESTILO VISUAL NBUS
# ──────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    html, body, [class*="css"] {{
        font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}

    .stApp {{
        background-color: {BG};
    }}

    .main .block-container {{
        padding-top: 2rem;
        max-width: 1100px;
    }}

    h1, h2, h3 {{
        font-weight: 700;
        color: {DARK} !important;
    }}

    p, label, .stMarkdown, .stCaption, span {{
        color: {DARK};
    }}

    hr {{
        border-color: {LINE};
    }}

    /* ---- Barra lateral ---- */
    [data-testid="stSidebar"] {{
        background-color: {DARK};
    }}
    [data-testid="stSidebar"] * {{
        color: #F2E9E7 !important;
    }}
    [data-testid="stSidebar"] img {{
        border-radius: 10px;
    }}
    [data-testid="stSidebar"] hr {{
        border-color: {DARK_BORDER};
    }}

    /* ---- Campo de texto ---- */
    .stTextInput > div > div > input {{
        background-color: #FFFFFF;
        color: {DARK};
        border: 1px solid {LINE};
        border-radius: 8px;
    }}
    .stTextInput > div > div > input:focus {{
        border-color: {RED};
        box-shadow: 0 0 0 1px {RED};
    }}

    /* ---- Botones ---- */
    .stButton > button {{
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.15s ease;
    }}
    .main .stButton > button {{
        background-color: {RED};
        color: #FFFFFF;
        border: none;
    }}
    .main .stButton > button:hover {{
        background-color: {RED_HOVER};
        color: #FFFFFF;
    }}
    /* Botones de preguntas frecuentes (van dentro de st.columns): look secundario */
    [data-testid="column"] .stButton > button {{
        background-color: #FFFFFF;
        color: {DARK};
        border: 1px solid {LINE};
        font-weight: 500;
    }}
    [data-testid="column"] .stButton > button:hover {{
        background-color: {RED_TINT};
        border-color: {RED};
        color: {DARK};
    }}

    /* ---- Caja de respuesta ---- */
    .respuesta-box {{
        background-color: #FFFFFF;
        color: {DARK};
        border-radius: 10px;
        padding: 20px;
        margin-top: 15px;
        border-left: 5px solid {RED};
        box-shadow: 0 1px 3px rgba(33,25,21,0.08);
    }}

    /* ---- Caja de código ---- */
    .codigo-box {{
        background-color: {DARK};
        color: #F2E9E7;
        border-radius: 8px;
        padding: 12px;
        font-family: 'Source Code Pro', monospace;
        font-size: 13px;
        margin-top: 10px;
        white-space: pre-wrap;
    }}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────
# CABECERA CORPORATIVA
# ──────────────────────────────────────────────────────────
st.markdown(f"""
<div style="
    background:#FFFFFF;
    border-radius:12px;
    border-left:7px solid {RED};
    padding:20px 26px;
    margin-bottom:28px;
    box-shadow:0 1px 4px rgba(33,25,21,0.08);
    display:flex;
    align-items:center;
    gap:18px;
">
    <img src="{LOGO_SRC}" style="height:50px;" />
    <div>
        <div style="font-weight:700; font-size:28px; color:{DARK}; letter-spacing:.2px; line-height:1.15;">
            Asistente Inteligente NBUS
        </div>
        <div style="font-size:14px; color:{GRAY_TEXT}; margin-top:2px;">
            Consulta en lenguaje natural la red de transporte interurbano de Navarra
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────
# BARRA LATERAL
# ──────────────────────────────────────────────────────────
with st.sidebar:
    if bus_disponible:
        st.markdown(
            f'<img src="{BUS_SRC}" style="width:100%; border-radius:10px;" />',
            unsafe_allow_html=True
        )
    else:
        st.caption("📁 Coloca bus_nbus.png en la carpeta static/ para ver la foto del autobús aquí.")

    st.markdown("#### Asistente NBUS")
    st.caption("TFM · Máster en Data Science, Business Analytics y Big Data")
    st.markdown("---")
    st.markdown(
        "Convierte preguntas en lenguaje natural sobre la red interurbana de "
        "Navarra en consultas sobre los datos reales de la red, generando y "
        "ejecutando el análisis necesario con un modelo de lenguaje."
    )
    st.markdown("---")
    st.caption("Datos: GTFS NBUS · INE · capas geográficas de Navarra")

# ──────────────────────────────────────────────────────────
# CARGA DE DATOS (cacheada para no recargar en cada pregunta)
# ──────────────────────────────────────────────────────────
@st.cache_data
def cargar_datos():
    df_rutas = pd.read_csv("resumen_por_ruta.csv")
    df_cobertura = pd.read_csv("cobertura_municipios.csv")
    df_clusters = pd.read_csv("output_clusters.csv")
    df_paradas = pd.read_csv("paradas_enriquecidas.csv")
    return df_rutas, df_cobertura, df_clusters, df_paradas

try:
    df_rutas, df_cobertura, df_clusters, df_paradas = cargar_datos()
    datos_ok = True
except FileNotFoundError as e:
    datos_ok = False
    st.error(f"No se encontraron los ficheros de datos: {e}")

# ──────────────────────────────────────────────────────────
# CONFIGURACIÓN DEL LLM
# ──────────────────────────────────────────────────────────
@st.cache_resource
def get_llm():
    # Importación diferida: langchain_openai es una librería pesada de importar.
    # Si se importara arriba del todo, retrasaría la carga inicial de la página
    # aunque el usuario aún no haya hecho ninguna pregunta.
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


def get_schema(df, name):
    cols = ", ".join([f"{c} ({df[c].dtype})" for c in df.columns])
    return f"{name} ({len(df)} filas): {cols}"


def construir_prompts(df_rutas, df_cobertura, df_clusters, df_paradas):
    schema = "\n".join([
        get_schema(df_rutas, "df_rutas"),
        get_schema(df_cobertura, "df_cobertura"),
        get_schema(df_clusters, "df_clusters"),
        get_schema(df_paradas, "df_paradas"),
    ])

    code_prompt = f"""Eres un generador de código Python para análisis de datos de transporte.

DataFrames disponibles:
{schema}

Notas importantes sobre las columnas:
- df_clusters tiene 'perfil_cluster' con valores: 'Sin servicio', 'Servicio estándar', 
  'Sobreservido', 'Hub secundario', 'Capital / Hub principal'
- Cuando el usuario pregunte por "zona crítica" o "mal cubiertos", interpreta como
  municipios con perfil_cluster = 'Sin servicio'
- df_cobertura tiene 'nivel_cobertura' con valores: 'Sin parada', 'Baja cobertura', 'Alta cobertura'

Genera SOLO el código Python necesario para responder la pregunta del usuario.
- Usa los nombres exactos: df_rutas, df_cobertura, df_clusters, df_paradas
- El código debe terminar con print() del resultado
- No añadas explicaciones, solo código Python puro
- No uses markdown ni backticks
"""

    answer_prompt = """Eres un analista experto en la red de transporte NBUS de Navarra.
Respondes SIEMPRE en español, de forma clara, breve y profesional.

Se te da una pregunta del usuario y el resultado bruto de una consulta a los datos.
Tu trabajo es convertir ese resultado en una respuesta natural y bien explicada,
como lo haría un analista de datos a su jefe. No menciones código ni DataFrames.
Si el resultado es una tabla, resúmela en frases claras, no la repitas tal cual.
"""
    return code_prompt, answer_prompt


def preguntar(pregunta, llm, code_prompt, answer_prompt,
              df_rutas, df_cobertura, df_clusters, df_paradas):
    # Paso 1: generar código
    response = llm.invoke([
        {"role": "system", "content": code_prompt},
        {"role": "user", "content": pregunta}
    ])
    codigo = response.content.strip().replace("```python", "").replace("```", "").strip()

    # Paso 2: ejecutar
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            exec(codigo, {
                "df_rutas": df_rutas,
                "df_cobertura": df_cobertura,
                "df_clusters": df_clusters,
                "df_paradas": df_paradas,
                "pd": pd,
            })
        resultado_bruto = buffer.getvalue()
    except Exception as e:
        resultado_bruto = f"Error al ejecutar el código: {e}"

    # Paso 3: redactar respuesta natural
    respuesta_final = llm.invoke([
        {"role": "system", "content": answer_prompt},
        {"role": "user", "content": f"Pregunta: {pregunta}\n\nResultado de la consulta:\n{resultado_bruto}"}
    ])

    return respuesta_final.content, codigo, resultado_bruto


# ──────────────────────────────────────────────────────────
# INTERFAZ PRINCIPAL
# ──────────────────────────────────────────────────────────
if datos_ok:

    if "pregunta_actual" not in st.session_state:
        st.session_state.pregunta_actual = ""

    st.subheader("💬 Preguntas frecuentes")

    ejemplos = [
        "¿Qué 5 rutas tienen más expediciones?",
        "¿Qué municipios están en zona crítica de cobertura?",
        "¿Qué rutas tienen más paradas bajo petición?",
        "¿Cuál es el municipio con más rutas que pasan?",
    ]

    cols = st.columns(len(ejemplos))
    for col, ejemplo in zip(cols, ejemplos):
        if col.button(ejemplo, use_container_width=True):
            st.session_state.pregunta_actual = ejemplo

    pregunta = st.text_input(
        "🔍 Escribe tu pregunta sobre la red NBUS:",
        value=st.session_state.pregunta_actual,
        placeholder="Ej: ¿Qué rutas tienen más demanda?"
    )

    mostrar_codigo = st.checkbox("Mostrar código generado (modo técnico)", value=False)

    if st.button("Preguntar al asistente", type="primary"):
        if pregunta.strip() == "":
            st.warning("Escribe una pregunta primero.")
        else:
            with st.spinner("Consultando los datos de NBUS..."):
                llm = get_llm()
                code_prompt, answer_prompt = construir_prompts(
                    df_rutas, df_cobertura, df_clusters, df_paradas
                )
                try:
                    respuesta, codigo, resultado_bruto = preguntar(
                        pregunta, llm, code_prompt, answer_prompt,
                        df_rutas, df_cobertura, df_clusters, df_paradas
                    )

                    st.markdown(f"""
                    <div class="respuesta-box">
                        <b>Respuesta:</b><br><br>{respuesta}
                    </div>
                    """, unsafe_allow_html=True)

                    if mostrar_codigo:
                        st.markdown("**Código ejecutado:**")
                        st.markdown(f"""
                        <div class="codigo-box">{codigo}</div>
                        """, unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"No he podido responder a esa pregunta: {e}")

    st.markdown("---")
    st.caption(
        "Asistente basado en LangChain + GPT-4o-mini · "
        "Datos: GTFS NBUS, INE, capas geográficas de Navarra · "
        "TFM Data Science & Big Data"
    )

else:
    st.info(
        "Coloca los ficheros resumen_por_ruta.csv, cobertura_municipios.csv, "
        "output_clusters.csv y paradas_enriquecidas.csv en la misma carpeta que esta app."
    )
