# Matching banco propio ↔ banco oficial del Ministerio — informe

- Preguntas nuestras: **2636**
- Con match ministerial: **1945** (73.8 %)
- De las emparejadas, con NORMA: **709** (36.5 %)
- Preguntas nuestras que acaban con norma: **709** (26.9 % del banco)

## Desglose por método

| Método | Nº | Con norma |
| --- | ---: | ---: |
| enunciado | 1913 | 699 |
| enunciado+respuesta | 32 | 10 |

## Motivos de no-match

| Motivo | Nº |
| --- | ---: |
| respuesta incompatible | 413 |
| score < umbral | 266 |
| zona gris sin confirmación de respuesta | 12 |

El veto por respuesta es intencionado: `token_set_ratio` puntúa 100 cuando el enunciado ministerial es un SUBCONJUNTO del nuestro (p. ej. «La potencia de un motor es:» dentro de «¿A qué equivale la potencia de un motor…?»), y esos son pares de preguntas DISTINTAS.

Dato para la Fase 2: **21** de las vetadas por respuesta tienen otro candidato con score ≥ umbral alto cuya respuesta sí casa; el algoritmo cerrado se queda con el candidato de score máximo y no las recupera.


## Cobertura por tema (nuestro)

| Tema | Preguntas | Con match | % | Con norma | % |
| --- | ---: | ---: | ---: | ---: | ---: |
| calidad-servicio | 59 | 31 | 52.5 % | 3 | 5.1 % |
| carga-estiba | 103 | 82 | 79.6 % | 11 | 10.7 % |
| conduccion-eficiente | 365 | 310 | 84.9 % | 0 | 0.0 % |
| entorno-economico | 174 | 123 | 70.7 % | 66 | 37.9 % |
| frenado-seguridad | 330 | 235 | 71.2 % | 4 | 1.2 % |
| motor-transmision | 184 | 155 | 84.2 % | 1 | 0.5 % |
| prevencion-riesgos | 73 | 45 | 61.6 % | 30 | 41.1 % |
| reglamentacion-documentos | 462 | 335 | 72.5 % | 302 | 65.4 % |
| salud-ergonomia | 259 | 219 | 84.6 % | 31 | 12.0 % |
| seguridad-vial-accidentes | 342 | 182 | 53.2 % | 33 | 9.6 % |
| tiempos-tacografo | 285 | 228 | 80.0 % | 228 | 80.0 % |

## Distribución del mejor score por pregunta nuestra

```
     0-50    |     0 | 
    50-60    |     3 | 
    60-70    |   106 | ##
    70-80    |   157 | ####
    80-85    |   134 | ###
    85-90    |   101 | ##
    90-95    |   153 | ###
    95-100   |   117 | ###
         100 |  1865 | ##########################################
```

## 10 no-emparejadas al azar (inspección humana)

- `cap-2d8b76b62e8e` — ¿Qué información debe facilitar el tacógrafo analógico de cada conductor?
- `cap-cf295b399d4f` — ¿Qué está considerado como manipulación del tacógrafo?
- `cap-72c8bde37fa3` — En la base de datos nacional de transportistas de animales deberán figurar, aparte de los datos de los propios transportistas,:
- `cap-00e9b590ed1a` — ¿Qué es la alcoholemia?
- `cap-29d4b8fc4347` — ¿Influye la temperatura en el consumo de combustible?
- `cap-d53e94fb5c96` — ¿Cuándo no es aconsejable utilizar el sistema de control de tracción?
- `cap-3bb1c84c5e48` — El humo del tabaco puede contribuir a provocar:
- `cap-56a5c5d4a34c` — ¿Qué clase de autorizaciones permiten el ejercicio de actividades complementarias del transporte?
- `cap-cce876641a8c` — ¿Cómo selecciona el conductor los datos fundamentales para sus decisiones durante la conducción?
- `cap-64f6cf8bbcdd` — ¿En qué condiciones deben efectuar la formación continua los conductores que realicen simultáneamente transporte de viajeros en autocar y transporte de mercancías con vehículos cuya conducción requiere estar en posesión del certificado de aptitud profesional (CAP)?
