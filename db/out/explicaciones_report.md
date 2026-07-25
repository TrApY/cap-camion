# Explicaciones y resúmenes (Gemini) — informe

Banco: **2636** preguntas · con explicación: **2617** (99.3 %) · modelo `gemini-2.5-flash`.

## Cobertura por origen de contexto

| Origen | Preguntas | % del banco | Con explicación | % del origen |
| --- | ---: | ---: | ---: | ---: |
| `norma+texto` | 529 | 20.1 % | 529 | 100.0 % |
| `norma` | 180 | 6.8 % | 180 | 100.0 % |
| `match` | 1236 | 46.9 % | 1236 | 100.0 % |
| `solo-banco` | 691 | 26.2 % | 672 | 97.3 % |
| **TOTAL** | **2636** | **100.0 %** | **2617** | **99.3 %** |

En **78** preguntas alguna opción se remite a otras por letra («Las respuestas A y B son correctas»). Como la lista va sin letras, esas referencias se sustituyen por el CONTENIDO de las opciones referidas antes de mandar el contexto al modelo.

## Validación automática (§5)

| Regla violada | Rechazos |
| --- | ---: |
| `letras` | 2 |
| `cita-inventada` | 0 |
| `cita-otra-norma` | 0 |
| **total de rechazos** | **2** |

- Preguntas que necesitaron regenerar: **2** (0.08 % del banco); de ellas **2** acabaron con explicación válida.

## Preguntas sin explicación final

| Motivo | Preguntas |
| --- | ---: |
| `sin-respuesta-correcta` | 19 |

`sin-respuesta-correcta`: el banco no tiene respuesta correcta y el Ministerio tampoco la aporta (sin match). No se genera nada: una explicación sin respuesta que explicar sería inventada.

## Longitud de las explicaciones

- Rango sano 120–900 caracteres · mediana **434** · mínimo 230 · máximo 821.
- Outliers (fuera de rango, no se rechazan): **0**

## Resúmenes por tema (§6)

Fuente normativa: Anexo I del RD 284/2021 (BOE-A-2021-6624), programa de cualificación inicial.

| Tema | Objetivos Anexo I | Preguntas en contexto | Palabras | Rechazos |
| --- | --- | ---: | ---: | ---: |
| El vehículo: motor y transmisión (`motor-transmision`) | 1.1 | 20 | 431 | 0 |
| Frenado y dispositivos de seguridad (`frenado-seguridad`) | 1.2 | 20 | 450 | 0 |
| Conducción eficiente y consumo (`conduccion-eficiente`) | 1.3 | 20 | 447 | 0 |
| Carga, estiba y masas (`carga-estiba`) | 1.5 | 20 | 420 | 0 |
| Tiempos de conducción y tacógrafo (`tiempos-tacografo`) | 2.1 | 20 | 451 | 0 |
| Entorno económico y organización (`entorno-economico`) | 3.7 | 20 | 394 | 0 |
| Documentos y reglamentación del transporte (`reglamentacion-documentos`) | 2.2 | 20 | 485 | 0 |
| Seguridad vial, accidentes y primeros auxilios (`seguridad-vial-accidentes`) | 1.4, 3.1, 3.5 | 20 | 448 | 0 |
| Salud, ergonomía y aptitud (`salud-ergonomia`) | 3.3, 3.4 | 20 | 387 | 0 |
| Prevención de riesgos (robos, tráfico ilegal) (`prevencion-riesgos`) | 3.2 | 20 | 458 | 0 |
| Calidad del servicio e imagen de empresa (`calidad-servicio`) | 3.6 | 20 | 391 | 0 |

Fuera del rango 300–500 palabras: ninguno.

## QA muestral (§7)

Muestra determinista (semilla `20260724`) de **529** explicaciones, juzgadas por Gemini en una llamada independiente.

| Estrato | ok | dudosa | mala |
| --- | ---: | ---: | ---: |
| `norma+texto` | 413 | 54 | 62 |
| `norma-o-match` | 0 | 0 | 0 |
| `solo-banco` | 0 | 0 | 0 |
| **TOTAL** | **413** | **54** | **62** |

Malas: **11.7%** (umbral 5%) → **BLOQUEO**.

### Motivos de las dudosas y malas

- `cap-0a4aa805ae13` — **dudosa** (norma+texto): La explicación es correcta y útil, pero no se basa en el artículo 41 del RD 1211/1990 proporcionado, el cual es irrelevante para la pregunta y la explicación.
- `cap-0bb843d9bf54` — **mala** (norma+texto): La explicación afirma que el Artículo 1.4 de la Ley 27/1999 especifica la composición de las cooperativas de primer y segundo grado, lo cual es falso, ya que dicho artículo solo menciona que pueden revestir esas formas, sin detallar su composición.
- `cap-0c777870bd44` — **mala** (norma+texto): La explicación basa su justificación en un apartado del Reglamento (UE) 165/2014 (Anexo I, apartado IV, c) cuyo texto literal no ha sido proporcionado, impidiendo su verificación.
- `cap-0e78bc0eab21` — **mala** (norma+texto): La explicación contradice la "Respuesta oficial" del Ministerio al afirmar que el límite de 2.000 kg de MMA es incorrecto y que el correcto es 3.500 kg.
- `cap-0ec46cfb821a` — **mala** (norma+texto): La explicación afirma que la comprobación "siempre" debe realizarse en presencia del cargador, lo cual contradice el Artículo 26.3 de la Ley 15/2009, que contempla alternativas si no es posible.
- `cap-10e696f6f009` — **dudosa** (norma+texto): La explicación basa parte de su justificación en una interpretación de la OM FOM/1882/2012 Anexo, 4.14, cuyo texto literal no ha sido proporcionado, impidiendo verificar si realmente se refiere a las responsabilidades del porteador como se afirma.
- `cap-10f2501e3994` — **dudosa** (norma+texto): La explicación afirma que el Reglamento Comunitario (UE) 165/2014 Anexo I, apartado IV, c establece el requisito, pero el texto legal literal proporcionado no incluye dicho apartado para su verificación.
- `cap-1131f98c194f` — **dudosa** (norma+texto): La explicación afirma que la infracción es muy grave, pero el texto legal proporcionado (Art. 55) solo establece las sanciones para las infracciones ya clasificadas, sin especificar si la infracción en cuestión es muy grave.
- `cap-117d9d431ddc` — **mala** (norma+texto): La explicación afirma incorrectamente que el período de presentación es de 56 días, cuando el texto legal establece 28 días anteriores más el día en curso.
- `cap-15f4a86212bb` — **dudosa** (norma+texto): La explicación introduce información sobre exenciones y requisitos del CAP que no está contenida ni es verificable con el único texto legal aportado (RD 1032/2007 Art. 4).
- `cap-1754f321654d` — **dudosa** (norma+texto): La explicación atribuye la frecuencia de 'cada dos años' al RD 640/2007 Art. 3, cuando este artículo solo establece la obligación de la revisión periódica, no su periodicidad específica.
- `cap-1cd712ef865b` — **mala** (norma+texto): La explicación atribuye falsamente las condiciones de exención del tacógrafo para el transporte de maquinaria al Artículo 2.n del RD 640/2007, cuyo contenido real es diferente y no se corresponde con dichas condiciones.
- `cap-1e69dd0fe750` — **mala** (norma+texto): La explicación contradice la respuesta oficial del Ministerio al afirmar efectos positivos de la declaración amistosa de accidente, y sus afirmaciones no están respaldadas por el texto legal proporcionado.
- `cap-1f01798e6226` — **dudosa** (norma+texto): La explicación introduce información sobre el plazo de 15 días y un escenario diferente que no está respaldado por el único texto legal proporcionado (Artículo 149 del Reglamento 952/2013), lo cual excede el alcance de la base legal dada.
- `cap-20f90022a480` — **mala** (norma+texto): La explicación cita incorrectamente el Art. 18.1 y el Anexo IV del RD 1032/2007 como base legal para las formas de acreditación de conductores de otros países, cuando la información relevante se encuentra en el Art. 18.4.
- `cap-217ff86969ec` — **dudosa** (norma+texto): La explicación basa su razonamiento en una afirmación sobre la aplicación de la normativa de transporte terrestre que no se encuentra en el texto legal proporcionado.
- `cap-2198bc526b97` — **dudosa** (norma+texto): La explicación afirma que ciertas enfermedades son reconocidas sin que el texto legal literal proporcionado las detalle explícitamente, excediendo la "única base legal" permitida.
- `cap-23bc627a2666` — **dudosa** (norma+texto): La explicación es correcta en su contenido, pero la información sobre el lugar de inmovilización no se deriva del texto legal literal del Art. 216.g del RD 1211/1990 proporcionado, el cual solo remite a otro artículo no incluido.
- `cap-23e8b172eefd` — **dudosa** (norma+texto): La explicación incluye información sobre la distancia de colocación y visibilidad de los triángulos que no se encuentra en el texto legal (RD 1428/2003 Art. 130.3) aportado como única base para la justificación.
- `cap-272c2551c472` — **mala** (norma+texto): La explicación afirma que las hojas de registro deben llevar la marca de homologación, lo cual no se encuentra en el texto legal literal proporcionado para el apartado IV, c, que en su lugar describe una marca para la correcta colocación de la hoja en el apartado III, c, 1.1.
- `cap-292895f56e04` — **mala** (norma+texto): La explicación atribuye falsamente la exigencia de anotar la matrícula del vehículo en el disco-diagrama al Reglamento Comunitario (UE) 165/2014 Anexo I, apartado IV, d, cuando el texto legal literal proporcionado para esa sección define la "circunferencia efectiva de los neumáticos de las ruedas" y no menciona la matrícula.
- `cap-301d52f9d5b5` — **mala** (norma+texto): La explicación induce a error al afirmar que los plazos de 12, 24 o 48 horas son para averías o pérdidas no manifiestas, cuando la Ley 15/2009 Art. 60 establece un plazo de siete días naturales para estas últimas.
- `cap-320fb53df967` — **mala** (norma+texto): La explicación cita un apartado (IV, b) que no existe en el texto legal proporcionado y la afirmación sobre la subdivisión de 20 km/h no se encuentra en las secciones relevantes del mismo.
- `cap-33316fa19d33` — **mala** (norma+texto): La explicación afirma que la información se establece en la OM FOM/1882/2012 Anexo, 8.5, pero el texto legal literal proporcionado no incluye la sección 8.5 ni la información mencionada.
- `cap-361e870abdf0` — **mala** (norma+texto): La explicación cita el Artículo 140.37 de la Ley 16/1987 y describe su contenido, pero el texto legal literal proporcionado para dicho artículo solo llega hasta el punto 15, haciendo que la justificación sea inverificable con la información dada.
- `cap-37ddda8254bd` — **dudosa** (norma+texto): La explicación es correcta y fiel a la respuesta, pero no se basa en el texto legal proporcionado, el cual no contiene las definiciones relevantes para justificarla.
- `cap-381b8ce934ef` — **mala** (norma+texto): La explicación afirma que la exención está "contemplada en la normativa", pero el texto legal literal proporcionado para el Reglamento Comunitario (CE) 561/2006 Art. 2.g no contiene ninguna mención a dicha exención, induciendo a error sobre el contenido de la base legal dada.
- `cap-39e0d89da427` — **mala** (norma+texto): La explicación afirma que la condición de que el transporte público forme parte del objeto social es la 'única' condición, lo cual es falso según el Artículo 43 de la Ley 16/1987 que lista múltiples requisitos.
- `cap-3a4e8cbdc017` — **dudosa** (norma+texto): La explicación afirma que el Art. 143.4 establece las infracciones específicas como causa de inmovilización, pero el texto legal proporcionado solo remite a puntos numerados de otros artículos (140 y 141) cuyo contenido no se ha facilitado, impidiendo la verificación directa de dicha afirmación.
- `cap-3ac2454f0447` — **mala** (norma+texto): La explicación afirma incorrectamente que treinta mil euros es el capital mínimo para una sociedad limitada, lo cual contradice el texto legal aportado (Art. 4.1 que establece un euro).
- `cap-3b32225ff281` — **mala** (norma+texto): La explicación atribuye incorrectamente la obligación de retirar el obstáculo en el menor tiempo posible al Artículo 130.2 del RD 1428/2003, cuando dicha obligación se encuentra en el Artículo 130.1.
- `cap-3e4c8e3497d4` — **dudosa** (norma+texto): La explicación es fiel a la respuesta correcta, pero el texto legal literal proporcionado no contiene la información necesaria para justificar la regla sobre el inicio de la responsabilidad del transportista.
- `cap-431a3281bd44` — **dudosa** (norma+texto): La explicación atribuye obligaciones específicas al Art. 2.1 que no se detallan explícitamente en el texto legal proporcionado.
- `cap-44dcc43ac4a6` — **dudosa** (norma+texto): La explicación afirma que la falta de título habilitante justifica la inmovilización según el Art. 143.4, pero el texto legal proporcionado de dicho artículo no detalla las infracciones a las que se refiere, haciendo la justificación incompleta.
- `cap-451258ab10a5` — **dudosa** (norma+texto): La explicación afirma la existencia y obligatoriedad de una placa descriptiva, así como su ubicación, pero el texto legal proporcionado como única base no menciona en absoluto dicha placa.
- `cap-4b142d85c2b8` — **mala** (norma+texto): La explicación basa su justificación en el Artículo 141.24 de la Ley 16/1987, cuyo contenido no se encuentra en el texto legal literal proporcionado como única base legal.
- `cap-4d52eb96ba6e` — **dudosa** (norma+texto): La explicación afirma el límite correcto pero no lo justifica con el texto legal de "RD 1561/1995 Art. 10" proporcionado, el cual no contiene directamente dicha limitación.
- `cap-4f570114d27c` — **dudosa** (norma+texto): La explicación afirma prohibiciones legales que, aunque correctas en el marco general de la Ley de Sociedades de Capital, no están explícitamente justificadas por los artículos 1.4 y 32 del RD Legislativo 1/2010 proporcionados como única base legal.
- `cap-51b40c725774` — **dudosa** (norma+texto): La explicación es imprecisa al afirmar que la prohibición "solo aplica si se compromete la seguridad", omitiendo la condición adicional de "fomentar las infracciones" presente en el texto legal del Artículo 10.1.
- `cap-51bbcce26968` — **mala** (norma+texto): La explicación se contradice al calificar la infracción como 'grave' después de haberla definido como 'muy grave', lo que induce a error.
- `cap-5203bdeaa768` — **dudosa** (norma+texto): La explicación hace afirmaciones sobre la inmovilización de vehículos basándose en puntos de los artículos 140 y 141, cuyo contenido no ha sido proporcionado en el texto legal, impidiendo su verificación.
- `cap-52c42b3bf78d` — **mala** (norma+texto): La explicación afirma falsamente que la sordera, la parálisis del nervio radial y la fatiga de vainas tendinosas están reconocidas en el RD 1299/2006 Anexo I, cuando el texto legal literal proporcionado de dicho anexo solo lista grupos generales de enfermedades y no estas condiciones específicas.
- `cap-54c649395e10` — **dudosa** (norma+texto): La explicación hace afirmaciones sobre los tiempos máximos de conducción y la ausencia de tolerancias que no están explícitamente detalladas en el Artículo 10 del Reglamento (CE) 561/2006, que es la única base legal proporcionada.
- `cap-552e3970f012` — **mala** (norma+texto): La explicación afirma que la definición de 'vehículo batería' se encuentra en el texto legal 'RD 2822/1998 Anexo II, C' proporcionado, pero dicha definición no aparece en el extracto legal literal.
- `cap-570de0d030c4` — **mala** (norma+texto): La explicación afirma que el RD 1561/1995 Art. 10.4 especifica claramente que "tiempo de presencia" es sinónimo de "tiempo de disponibilidad", lo cual no se desprende literalmente del texto legal aportado, que solo describe la condición de disponibilidad del trabajador durante el tiempo de presencia.
- `cap-596e7cca4200` — **mala** (norma+texto): La explicación atribuye al Anexo 10.2 de la OM FOM/1882/2012 una autorización que no se encuentra en el texto legal literal proporcionado para dicho artículo.
- `cap-59d0f965ba1b` — **dudosa** (norma+texto): La explicación asume la clasificación de la carencia de autorización como infracción muy grave y generaliza las condiciones de inmovilización del Art. 143.4.a, sin que estos hechos se deriven explícitamente del texto legal proporcionado.
- `cap-5bdb54cfdc70` — **mala** (norma+texto): La explicación basa su afirmación principal en el contenido del punto 5.4 del Anexo de la OM FOM/1882/2012, pero dicho texto legal no ha sido proporcionado como parte de la "única base legal que puedes usar", impidiendo verificar la fidelidad de la explicación a la norma citada.
- `cap-601d0bd6e96d` — **mala** (norma+texto): La explicación clasifica las infracciones como "graves" cuando el Artículo 140 las define como "muy graves", y cita sub-artículos (140.22 y 140.35) cuyo contenido no aparece en el texto legal literal proporcionado.
- `cap-60ca209ff436` — **mala** (norma+texto): La explicación contradice la respuesta oficial del Ministerio al clasificar la infracción como "muy grave" en lugar de "grave".
- `cap-627df748c825` — **dudosa** (norma+texto): La explicación afirma que la definición es 'exactamente' como la normativa, pero omite una parte de la definición legal del 'tiempo diario de conducción' según el Artículo 4.k del Reglamento (CE) 561/2006.
- `cap-642e51ba36d0` — **dudosa** (norma+texto): La explicación se basa en el RD 1299/2006 Anexo I para justificar la inclusión o exclusión de enfermedades, pero el texto legal literal proporcionado solo lista grupos generales y no el detalle de las enfermedades específicas.
- `cap-65df9be58a06` — **mala** (norma+texto): La explicación afirma que el Reglamento Comunitario (UE) 165/2014 Anexo I, apartado IV, d, establece la obligación de anotar el kilometraje inicial y final en el disco, pero esta información no se encuentra en el texto legal literal proporcionado para dicha referencia.
- `cap-691c6e13a37b` — **mala** (norma+texto): La explicación afirma falsamente que no se deben registrar los datos del vehículo en la hoja de registro, lo cual contradice directamente el Artículo 34.6 del Reglamento (UE) 165/2014.
- `cap-6dbce9b88230` — **dudosa** (norma+texto): La explicación justifica la respuesta citando el Artículo 140.37 de la Ley 16/1987, pero el texto legal literal proporcionado está truncado y no incluye dicho punto, impidiendo verificar la afirmación.
- `cap-7125b44bb553` — **mala** (norma+texto): La explicación afirma que la normativa permite dividir los periodos en dos días consecutivos, pero esta flexibilidad no se menciona en el texto literal del RD 1032/2007 Art. 7.2 proporcionado.
- `cap-72f4b25773c8` — **mala** (norma+texto): La explicación atribuye un contenido específico al Artículo 142.17 que no se encuentra en el texto legal literal proporcionado como única base.
- `cap-7605dc5fec81` — **mala** (norma+texto): La explicación afirma incorrectamente que el Artículo 226 del Reglamento (UE) 952/2013 establece el régimen de tránsito interno, cuando dicho artículo se refiere exclusivamente al tránsito externo.
- `cap-79557dc16903` — **dudosa** (norma+texto): La explicación afirma que el Reglamento Comunitario (UE) 165/2014 Anexos I y IB exige revisiones periódicas y calibraciones, pero el texto legal literal proporcionado de dichos anexos no detalla explícitamente esta exigencia.
- `cap-7a72d93682cd` — **dudosa** (norma+texto): La explicación afirma que la gripe A no encaja en 'categorías específicas' del RD 1299/2006 Anexo I, pero el texto legal literal proporcionado solo lista los grupos, no las categorías específicas, lo que implica un conocimiento externo no dado.
- `cap-7bbecde0156a` — **dudosa** (norma+texto): La explicación afirma un requisito legal que no puede ser verificado con el texto legal literal aportado, ya que la sección citada (Anexo I, apartado IV, c) no está presente en el extracto.
- `cap-7d1a25563a75` — **dudosa** (norma+texto): La explicación es fiel a la respuesta correcta de la pregunta, pero ignora completamente el texto legal aportado por ser irrelevante para el tema de las agencias de transporte, lo que la hace incompleta en el contexto dado.
- `cap-821274cdfd16` — **dudosa** (norma+texto): La explicación añade detalles sobre los términos de integración de los vehículos (propiedad, arrendamiento financiero o arrendamiento ordinario) que no están explícitamente en el texto legal del Artículo 102 proporcionado, sino que son referenciados por un artículo (54.2) que no se ha facilitado.
- `cap-88259999c015` — **mala** (norma+texto): La explicación contradice la respuesta correcta indicada en la pregunta (2,5 toneladas) al afirmar que es incorrecta, aunque se alinea con el texto legal y la respuesta oficial del Ministerio (3,5 toneladas).
- `cap-89bfe23b379a` — **dudosa** (norma+texto): La explicación afirma la obligación de los agentes de tráfico sin que el texto legal aportado (Art. 129 del RD 1428/2003) la establezca explícitamente, aunque sea correcta en un contexto más amplio.
- `cap-8f075008e374` — **dudosa** (norma+texto): La explicación no aborda la discrepancia entre el período de 56 días mencionado en la pregunta y el período de 28 días establecido en el Reglamento Comunitario (UE) 165/2014 Art. 36.2, lo que la hace imprecisa e incompleta para el alumno.
- `cap-8f391bb98e32` — **mala** (norma+texto): La explicación cita incorrectamente el artículo 4.2.b del RD Legislativo 8/2004 para los daños a las personas, cuando la información correcta se encuentra en el artículo 4.2.a.
- `cap-90727554e347` — **dudosa** (norma+texto): La explicación cita el Artículo 140.35 de la Ley 16/1987 y afirma su contenido, pero el texto literal de dicho artículo no se encuentra entre los datos legales proporcionados para su verificación.
- `cap-91656139623c` — **mala** (norma+texto): La explicación basa su justificación en un apartado del Reglamento Comunitario (UE) 165/2014 (Anexo I, apartado IV, d) cuyo texto literal no ha sido proporcionado, impidiendo su verificación con la única base legal permitida.
- `cap-94c0f5838d9a` — **mala** (norma+texto): La explicación cita incorrectamente el Artículo 140.34, que no está presente en el texto legal proporcionado como única base, y la justificación de la infracción es una interpretación forzada.
- `cap-9ad57d29ceb8` — **dudosa** (norma+texto): La explicación utiliza 'zona más interior' en lugar de 'zona más céntrica', que es el término exacto de la respuesta oficial del Ministerio, lo que la hace imprecisa.
- `cap-9b076ced039c` — **mala** (norma+texto): La explicación atribuye incorrectamente el "falseamiento de documentos de control" al Artículo 140.22 de la Ley 16/1987, cuando el texto legal proporcionado para dicho artículo se refiere a la negativa u obstrucción a la actuación de los Servicios de Inspección, y el falseamiento de documentos de control se encuentra en el Artículo 140.9.
- `cap-9d4b9983e4ca` — **dudosa** (norma+texto): Aunque la explicación es factualmente correcta y fiel a la respuesta, el texto legal aportado (Reglamento Comunitario (UE) 165/2014 Art. 13) es insuficiente para justificar las afirmaciones sobre los tipos de tacógrafos y sus consumibles, lo que la hace incompleta en su fundamentación legal.
- `cap-9daf9e6cfe01` — **dudosa** (norma+texto): La explicación usa 'asegurado' para definir quién paga la prima, pero luego cita la ley que especifica que el 'tomador' es quien está obligado al pago, sin aclarar la relación o distinción entre ambas figuras, lo que puede generar imprecisión.
- `cap-9e969afc5674` — **mala** (norma+texto): La explicación se refiere directamente a una de las opciones de la pregunta, lo cual es inaceptable.
- `cap-9f1cd71ccb7f` — **mala** (norma+texto): La explicación afirma que el Reglamento Comunitario (CE) 1/2005 Anexo I establece la separación de animales con y sin cuernos, pero esta disposición no se encuentra en el texto legal literal proporcionado.
- `cap-9fae3139c910` — **dudosa** (norma+texto): La explicación afirma la respuesta correcta y descarta las incorrectas, pero la necesidad de la autorización administrativa no se justifica con el texto legal del Artículo 41 del RD 1211/1990 que se proporciona, lo que la hace incompleta en su fundamentación.
- `cap-a1ab3e86010c` — **dudosa** (norma+texto): La explicación se basa en una sección de la normativa (3.3) que no está incluida en el texto legal proporcionado, impidiendo verificar su afirmación.
- `cap-a20b8bf99449` — **dudosa** (norma+texto): La explicación es correcta y útil, pero la afirmación principal sobre la marca de homologación en las hojas de registro no está explícitamente contenida en el texto legal literal proporcionado, que es la única base legal permitida.
- `cap-a42ec9bb4471` — **dudosa** (norma+texto): La explicación omite la salvedad del texto legal sobre la obligatoriedad de satisfacer los gastos generados por la práctica de pruebas, lo que la hace imprecisa.
- `cap-a800e271270f` — **mala** (norma+texto): La explicación afirma incorrectamente que el plazo de 5 días se refiere a las alegaciones de la parte reclamada cuando el texto legal indica 10 días para ese fin.
- `cap-af40406bdda6` — **mala** (norma+texto): La explicación afirma falsamente que el cuentarrevoluciones no es un elemento obligatorio del tacógrafo analógico, lo cual contradice el texto legal que lo incluye como dispositivo indicador obligatorio.
- `cap-b2a07b41e5e4` — **dudosa** (norma+texto): La explicación afirma que las pinzas están prohibidas por la normativa, pero el texto legal proporcionado (Art. 116 del RD 1428/2003) no menciona ni prohíbe explícitamente el uso de pinzas en el cinturón de seguridad.
- `cap-b5a1a3c63205` — **mala** (norma+texto): La explicación atribuye la regla de fraccionamiento de la pausa al texto legal del Artículo 8 proporcionado, el cual no contiene dicha información.
- `cap-b709d97b1926` — **dudosa** (norma+texto): La explicación introduce un límite de 56 horas semanales no presente en el texto legal aportado y el artículo citado (141.24) se refiere a la falta de consignación de datos, no al exceso de horas de conducción.
- `cap-be0076c949de` — **mala** (norma+texto): La explicación atribuye una regla específica (minoración en más del 50% de los descansos) al Art. 140.37 que no aparece en el texto legal proporcionado y, además, realiza un cálculo incorrecto al afirmar que el descanso se ha reducido en más del 50%.
- `cap-beabe8c1b43e` — **mala** (norma+texto): La explicación justifica la exención con razones no contenidas en el Artículo 41 del RD 1211/1990, la única base legal proporcionada.
- `cap-bfdd1f3f1ebd` — **mala** (norma+texto): La explicación atribuye una afirmación legal específica al Artículo 140.22 de la Ley 16/1987, pero el texto literal de dicho artículo no se encuentra en la "única base legal" proporcionada para su verificación.
- `cap-c32b7acc439a` — **dudosa** (norma+texto): La explicación es correcta en su contenido, pero no se apoya en el texto legal proporcionado, el cual es irrelevante para la pregunta y no justifica la afirmación.
- `cap-c32eb1385ffa` — **dudosa** (norma+texto): La explicación afirma que la normativa establece que el tiempo de trabajo abarca todas las actividades laborales independientemente de para cuántos empleadores se realicen, pero esta afirmación específica no se encuentra explícitamente en el Artículo 10 del RD 1561/1995 proporcionado.
- `cap-c492edf65762` — **mala** (norma+texto): La explicación atribuye incorrectamente a la sección III.c del Reglamento la obligación de tener dispositivos de registro para distancia, velocidad y apertura de caja, cuando esta información se encuentra en la sección III.a.
- `cap-c56769a039e2` — **dudosa** (norma+texto): La explicación es fiel a la respuesta correcta, pero su justificación legal no puede ser verificada con el texto legal aportado, que está truncado y no incluye el apartado relevante.
- `cap-c56b967eeeec` — **mala** (norma+texto): La explicación atribuye incorrectamente la base legal al citar el apartado III, c.4 para una afirmación que se encuentra en el apartado II del mismo anexo en el texto legal proporcionado.
- `cap-c85d5ec8402c` — **mala** (norma+texto): La explicación afirma que el Reglamento Comunitario (UE) 165/2014 Anexo I, apartado IV, c, establece la obligatoriedad de los datos del fabricante, pero el texto legal literal proporcionado para dicho apartado no contiene esa información.
- `cap-cd21f11cb829` — **dudosa** (norma+texto): La explicación es imprecisa al describir la condición de los 30 kilómetros de recorrido, ya que la ley establece una limitación general de 30 km de ida, salvo si es en el mismo sentido de la marcha, donde no hay limitación.
- `cap-d0129167cd03` — **mala** (norma+texto): La explicación afirma falsamente que la ley establece un mínimo fijo para las infracciones muy graves y que la sanción no depende del número de viajeros, cuando el texto legal muestra excepciones donde sí puede depender del número de viajeros.
- `cap-d25d1e24674b` — **mala** (norma+texto): La explicación es falsa porque afirma que todas las opciones son correctas, lo cual contradice directamente la respuesta oficial del Ministerio que indica que todas son incorrectas.
- `cap-d58c33fe23b7` — **dudosa** (norma+texto): La explicación basa su justificación legal en un apartado del reglamento cuyo texto literal no ha sido proporcionado, lo que impide su verificación.
- `cap-d5b2a3059def` — **mala** (norma+texto): La explicación afirma que la OM INT/2223/2014 Anexo II, A) 1 establece los daños materiales como criterio para un accidente de tráfico, lo cual contradice el texto legal literal de dicho punto que solo menciona personas fallecidas o heridas.
- `cap-d6be1026790c` — **mala** (norma+texto): La explicación introduce cantidades específicas de capacidad financiera (9.000 y 5.000 euros) que no se mencionan en el texto legal literal del Artículo 43 de la Ley 16/1987 proporcionado.
- `cap-d6f8b7ca9919` — **mala** (norma+texto): La explicación afirma falsamente que una de las opciones correctas, que describe mercancías de la Unión según el artículo 5(23)(b) del Reglamento (UE) 952/2013, es incorrecta.
- `cap-d76d5983f850` — **mala** (norma+texto): La explicación afirma que las enfermedades profesionales deben tener una alta ocurrencia, lo cual no se menciona en la definición legal proporcionada en los artículos 157 y 316 del RD Legislativo 8/2015.
- `cap-d7dfa083fcda` — **mala** (norma+texto): La explicación afirma falsamente que la función de los cascos se detalla en el Anexo I del RD 773/1997, cuando el texto legal aportado no contiene dicha información.
- `cap-dc73a79138f8` — **dudosa** (norma+texto): La explicación es fiel al texto legal al referirse al 'descanso diario normal', pero no aborda la discrepancia con la pregunta que menciona el 'descanso semanal reducido', lo que puede generar confusión al alumno.
- `cap-e0652fea6182` — **dudosa** (norma+texto): La explicación afirma que el Reglamento Comunitario (UE) 165/2014 Anexo I, apartado III, c, establece cómo se registran los datos de forma que la línea sea quebrada, pero el texto legal proporcionado no describe la apariencia visual de la línea ni justifica la naturaleza 'discontinua' del registro que llevaría a una línea quebrada.
- `cap-e26a0b52270d` — **mala** (norma+texto): La explicación atribuye permisos y prohibiciones específicas al Anexo I del Reglamento (CE) 1/1/2005 que no aparecen en el texto legal literal proporcionado.
- `cap-e2cb5f85d134` — **mala** (norma+texto): La explicación afirma que el Reglamento Comunitario (UE) 165/2014 Anexo I, apartado IV, a.2 establece la capacidad de 24 horas, pero el texto legal literal proporcionado para esa referencia no contiene dicha información.
- `cap-e436edfb34ae` — **dudosa** (norma+texto): La explicación afirma el contenido del Artículo 140.20 de la Ley 16/1987, pero dicho artículo no se encuentra en el texto legal literal proporcionado, impidiendo la verificación de su fidelidad.
- `cap-e4f63892c2e5` — **mala** (norma+texto): La explicación afirma el contenido del Artículo 140.22 de la Ley 16/1987, pero dicho texto legal no se ha proporcionado en su totalidad, impidiendo la verificación de la afirmación.
- `cap-ebb51d2bd4f4` — **mala** (norma+texto): La explicación basa su afirmación principal en el contenido del punto 10.3 del Anexo de la OM FOM/1882/2012, cuyo texto literal no ha sido proporcionado para su verificación.
- `cap-ecdef4bd2691` — **dudosa** (norma+texto): La explicación afirma que la normativa establece un control cada dos años, pero esta afirmación no puede ser verificada con el texto legal literal proporcionado, ya que está truncado y no incluye los apartados relevantes (VI, 3 y VI, 4).
- `cap-edf7c74ec55d` — **dudosa** (norma+texto): La explicación es imprecisa al afirmar que a partir de la tercera hora de espera de carga o descarga se considera tiempo de trabajo efectivo si la duración es previsible, ya que omite la salvedad de que esto puede variar según convenios colectivos si se conoce de antemano su duración previsible, según el Art. 10.4.c del RD 1561/1995.
- `cap-eeff6a9611e2` — **mala** (norma+texto): La explicación afirma que el conductor puede acceder a sus propios datos en cualquier momento, lo cual no está respaldado por el Artículo 4.5 del Reglamento (UE) 165/2014, que solo concede explícitamente este acceso en cualquier momento a las autoridades de control y a la empresa de transporte.
- `cap-ef93f5ba5b1b` — **mala** (norma+texto): La explicación afirma un hecho que no está contenido ni es derivable del texto legal aportado (RD 1211/1990 Art. 41), el cual es completamente irrelevante para la pregunta y la respuesta.
- `cap-fa68d2d2e2ba` — **mala** (norma+texto): La explicación afirma incorrectamente que diez años es el periodo de vigencia del permiso de conducir para las categorías profesionales, lo cual es falso en el contexto de conductores profesionales.
- `cap-fc42e013dfe3` — **dudosa** (norma+texto): La explicación justifica la respuesta basándose en que el RD 1299/2006 Anexo I incluye enfermedades por agentes físicos y que el ruido es un agente físico, pero el texto legal literal proporcionado no especifica que la sordera por ruido esté explícitamente reconocida bajo ese grupo.

## Tokens y coste

| Etapa | Llamadas | Entrada | Salida | Pensamiento | Coste $ |
| --- | ---: | ---: | ---: | ---: | ---: |
| explicaciones | 2670 | 1,585,228 | 265,990 | 0 | 1.1405 |
| resumenes | 11 | 14,340 | 6,068 | 23,617 | 0.0785 |
| qa | 561 | 736,750 | 28,899 | 769,774 | 2.2177 |
| **TOTAL** | **3242** | **2,336,318** | **300,957** | **793,391** | **3.4368** |

Tarifa aplicada: 0.30 $/M entrada y 2.50 $/M salida (las *thoughts* se facturan como salida). El coste incluye las llamadas rechazadas y regeneradas.

