# Analizador EEFF IFRS

Prototipo determinístico para analizar estados financieros IFRS publicados en
XBRL. El primer caso de prueba incluido es **Aguas Andinas S.A. — consolidado,
12/2025**.

## Alcance de esta primera versión

- Lee instancias XBRL desde un ZIP o desde una carpeta extraída.
- Conserva contexto, período, unidad, dimensiones, precisión y etiqueta.
- Construye una vista de EEFF con cuentas IFRS principales.
- Deja visibles las hojas futuras: Análisis, Histórico, Industria e
  Interpretación.

No descarga archivos desde la CMF, no procesa PDF y no llama a ningún modelo de
IA. Esos puntos se incorporarán sobre las interfaces indicadas en el código.

## Ejecutar

Use el Python que tenga instalado y ejecute:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

La aplicación abre por defecto el caso de prueba incluido en
`data/raw/aguas_andinas_2025_12_xbrl.zip`. Puede reemplazarlo temporalmente
cargando otro ZIP XBRL desde la barra lateral.

## Estructura

```text
app.py                         interfaz Streamlit
src/eeff_analyzer/xbrl.py      motor XBRL determinístico
src/eeff_analyzer/models.py    modelos de datos
src/eeff_analyzer/catalog.py   cuentas IFRS iniciales
src/eeff_analyzer/llm.py       contrato futuro para IA (sin API)
data/raw/                      insumos locales de prueba
tests/                         pruebas del motor
```
