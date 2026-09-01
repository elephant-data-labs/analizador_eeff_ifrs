"""Catálogo pequeño, explícito y ampliable de cuentas IFRS para la portada EEFF."""

FINANCIAL_STATEMENT_CATALOG = [
    ("Estado de situación financiera", "Assets", "Activos totales"),
    ("Estado de situación financiera", "CurrentAssets", "Activos corrientes"),
    ("Estado de situación financiera", "CashAndCashEquivalents", "Efectivo y equivalentes al efectivo"),
    ("Estado de situación financiera", "TradeAndOtherCurrentReceivables", "Deudores comerciales y otras cuentas por cobrar"),
    ("Estado de situación financiera", "Inventories", "Inventarios"),
    ("Estado de situación financiera", "Liabilities", "Pasivos totales"),
    ("Estado de situación financiera", "CurrentLiabilities", "Pasivos corrientes"),
    ("Estado de situación financiera", "Equity", "Patrimonio"),
    ("Estado de resultados", "Revenue", "Ingresos de actividades ordinarias"),
    ("Estado de resultados", "ProfitLossFromOperatingActivities", "Resultado operacional"),
    ("Estado de resultados", "FinanceCosts", "Gastos financieros"),
    ("Estado de resultados", "ProfitLoss", "Ganancia (pérdida)"),
    ("Estado de flujos de efectivo", "CashFlowsFromUsedInOperatingActivities", "Flujo operacional"),
]

# Conceptos que NO son montos en pesos y por eso quedan fuera del catálogo anterior:
# no deben redondearse a millones ni corregirse por IPC. Se muestran aparte.
NON_MONETARY_CATALOG = [
    ("Acciones", "NumberOfSharesOutstanding", "Número de acciones suscritas y pagadas"),
]

