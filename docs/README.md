# Flujos del miner

Cada archivo PlantUML describe un comando de la CLI:

| Diagrama | Flujo |
| --- | --- |
| [clone.puml](clone.puml) | `clone-repositories`: consultar y clonar repositorios; guardar rutas y fallos en `clones.json`. |
| [analyze.puml](analyze.puml) | `analyze-code`: analizar clones existentes con CodeQL y consolidar SARIF. |
| [sbom.puml](sbom.puml) | `generate-sbom`: generar CycloneDX con Syft y un reporte por organización. |
| [vulnerabilities.puml](vulnerabilities.puml) | `scan-dependency-vulnerabilities`: examinar dependencias de SBOM con Grype. |

Abre los `.puml` con un visor de PlantUML. También puedes generar SVG si tienes
Java y el JAR de PlantUML instalados:

```powershell
java -jar C:\tools\plantuml.jar -tsvg "docs/*.puml"
```

`analyze-code` y `generate-sbom` comparten `load_latest_clones`: sin
`--run-id` seleccionan la clonación más reciente; con él buscan el sufijo exacto
de `clone-`. `scan-dependency-vulnerabilities` selecciona una ejecución SBOM
por el sufijo de `sbom-`.
Los errores globales terminan el comando; los fallos por repositorio se registran
y permiten continuar con los demás. Ninguno de estos dos comandos vuelve a clonar.
