# Flujos del miner

Cada archivo PlantUML describe un comando de la CLI:

| Diagrama | Flujo |
| --- | --- |
| [list.puml](list.puml) | Consultar repositorios mediante la API de GitHub. |
| [clone.puml](clone.puml) | Clonar y guardar las rutas y los fallos en `clones.json`. |
| [analyze.puml](analyze.puml) | Analizar clones existentes con CodeQL y consolidar SARIF. |
| [sbom.puml](sbom.puml) | Generar CycloneDX con Syft y un reporte por organización. |

Abre los `.puml` con un visor de PlantUML. También puedes generar SVG si tienes
Java y el JAR de PlantUML instalados:

```powershell
java -jar C:\tools\plantuml.jar -tsvg "docs/*.puml"
```

`analyze` y `sbom` comparten `load_latest_clones`: sin `--run-id` seleccionan la
clonación más reciente; con él buscan el sufijo exacto de `scan-` o `clone-`.
Los errores globales terminan el comando; los fallos por repositorio se registran
y permiten continuar con los demás. Ninguno de estos dos comandos vuelve a clonar.
