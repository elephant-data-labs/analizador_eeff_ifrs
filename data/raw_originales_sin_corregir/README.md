# Originales sin corregir

Esta carpeta guarda copias sin modificar de archivos XBRL de `data/raw` en los que
se detectó y corrigió un error dentro del propio archivo fuente. No se usan en la
aplicación (`load_local_cases` solo lee ZIP directamente desde `data/raw`, no
recorre subcarpetas): quedan aquí únicamente como respaldo y evidencia de la
corrección.

## aguas_andinas_2022_12_xbrl_RUT_original_90413000-1.zip

**Problema detectado:** los 824 contextos del archivo `61808000_202212_C.xbrl`
(dentro del ZIP `aguas_andinas_2022_12_xbrl.zip`) declaraban el RUT
`90413000-1` en `<xbrli:identifier scheme="http://www.cmfchile.cl/RUT">`. Ese
RUT corresponde a Compañía Cervecerías Unidas S.A. (CCU) según el registro de
la CMF, no a Aguas Andinas (RUT real: `61808000-5`).

**Verificación:** los montos del archivo (Activos: $2.379.349.560.000 :
Patrimonio: $838.891.099.000 : Ingresos: $575.465.445.000 : Ganancia:
$85.250.874.000) coinciden exactamente, peso por peso, con los Estados
Financieros Consolidados oficiales de Aguas Andinas S.A. al 31 de diciembre de
2022, publicados en su propio sitio de inversionistas:
https://www.aguasandinasinversionistas.cl/~/media/Files/A/Aguas-IR-v2/financial-statements/en/2022/aguas-andinas-ifrs-consolidated-financial-statements-december-2022-en.pdf

Además, el nombre interno de los archivos dentro del ZIP ya usaba el prefijo
`61808000` (RUT de Aguas Andinas sin dígito verificador), lo que confirma que
el contenido es de Aguas Andinas y que el error fue solo en la etiqueta de RUT
dentro del XML, no una descarga equivocada de otra empresa.

**Corrección aplicada:** se reemplazó la cadena `90413000-1` por `61808000-5`
dentro del archivo `.xbrl` (a nivel de bytes, sin tocar su codificación
ISO-8859-1 ni ningún otro archivo del ZIP). El ZIP corregido quedó en
`data/raw/aguas_andinas_2022_12_xbrl.zip`; esta carpeta conserva el original
sin tocar por trazabilidad.
