# Textos normativos para el RAG — informe

Universo: normas base con **>= 4 referencias** en `ministerio_match.json`.

- Referencias normativas del match: **709**
- Normas base distintas: **67** (39 en el universo, 28 de cola larga)
- Referencias del universo: **671**

## Número clave

De las **709** referencias del banco oficial, **522** (73.6 %) quedan con el texto de su artículo disponible para el RAG.
Contando también las que tienen extraído solo parte de los artículos que citan: 529 (74.6 %).

### Desglose de las no cubiertas

| Motivo | Referencias |
| --- | ---: |
| norma no-resuelta | 106 |
| cola larga (norma con < 4 referencias) | 38 |
| artículo citado no extraíble del texto | 33 |
| artículo citado solo parcialmente extraído | 7 |
| referencia sin localizador extraíble | 3 |

### Huecos concretos: qué artículo citado falta y en qué norma

| Norma resuelta | Objetivo citado | Referencias afectadas |
| --- | --- | ---: |
| Reglamento Comunitario (UE) 165/2014 | Anexo IB | 40 |
| Reglamento Comunitario (CE) 561/2006 | Considerando | 1 |
| Ley 16/1987 | Título IV | 1 |
| RD 1032/2007 | Disposición transitoria 1ª | 1 |

El objetivo citado no está en el documento resuelto: o la cita ministerial apunta a una parte de OTRA norma (las que llevan la norma derogada entre paréntesis, p. ej. `(3821/85)`), o es un tipo de localizador que esta fase no extrae (títulos, capítulos, considerandos, disposiciones).


## Normas del universo

| Norma | Refs | Estado | Fuente | Id | Arts. citados | Extraídos |
| --- | ---: | --- | --- | --- | ---: | ---: |
| Reglamento Comunitario (UE) 165/2014 | 108 | ok | eurlex | 32014R0165 | 17 | 16 |
| Ley 16/1987 | 96 | ok | boe | BOE-A-1987-17803 | 20 | 20 |
| Reglamento Comunitario (CE) 561/2006 | 67 | ok | eurlex | 32006R0561 | 12 | 12 |
| RD 1032/2007 | 29 | ok | boe | BOE-A-2007-14726 | 11 | 11 |
| Acuerdo ATP | 27 | no-resuelta | — | — | 4 | 0 |
| Reglamento Comunitario (UE) 952/2013 | 27 | ok | eurlex | 32013R0952 | 19 | 19 |
| Convenio CMR | 25 | no-resuelta | — | — | 14 | 0 |
| RD 1211/1990 | 22 | ok | boe | BOE-A-1990-24442 | 7 | 7 |
| Reglamento Comunitario (CE) 1072/2009 | 18 | ok | eurlex | 32009R1072 | 5 | 5 |
| RD 640/2007 | 17 | ok | boe | BOE-A-2007-10557 | 2 | 2* |
| RD Legislativo 1/2010 | 13 | ok | boe | BOE-A-2010-10544 | 11 | 11 |
| OM FOM/1190/2005 | 12 | ok | boe | BOE-A-2005-7137 | 7 | 7* |
| RD 773/1997 | 12 | ok | boe | BOE-A-1997-12735 | 5 | 5* |
| Convenio CIDE | 11 | no-resuelta | — | — | 5 | 0 |
| Convenio TIR | 11 | no-resuelta | — | — | 9 | 0 |
| Ley Orgánica 4/2000 | 11 | ok | boe | BOE-A-2000-544 | 4 | 4 |
| RD 1561/1995 | 11 | ok | boe | BOE-A-1995-21346 | 3 | 3 |
| RD Legislativo 8/2004 | 11 | ok | boe | BOE-A-2004-18911 | 5 | 5 |
| Ley 50/1980 | 10 | ok | boe | BOE-A-1980-22501 | 7 | 7 |
| RD Legislativo 8/2015 | 10 | ok | boe | BOE-A-2015-11724 | 3 | 3 |
| Ley 15/2009 | 9 | ok | boe | BOE-A-2009-18004 | 9 | 9 |
| Ley 31/1995 | 9 | ok | boe | BOE-A-1995-24292 | 7 | 7 |
| OM FOM/734/2007 | 9 | ok | boe | BOE-A-2007-6514 | 8 | 8 |
| RD 1428/2003 | 9 | ok | boe | BOE-A-2003-23514 | 5 | 5 |
| Convenio Aplicación del Acuerdo de Schengen | 8 | no-resuelta | — | — | 5 | 0 |
| Ley 27/1999 | 8 | ok | boe | BOE-A-1999-15681 | 5 | 5 |
| OM FOM/1882/2012 | 8 | ok | boe | BOE-A-2012-11324 | 1 | 1 |
| Reglamento Comunitario (UE) 2015/2447 | 8 | ok | eurlex | 32015R2447 | 7 | 7 |
| Reglamento Comunitario (CE) 1/2005 | 7 | ok | eurlex | 32005R0001 | 5 | 5 |
| Resolución D.G. Tráfico 01/06/2009 | 7 | no-resuelta | — | — | 1 | 0 |
| RD 2822/1998 | 6 | ok | boe | BOE-A-1999-1826 | 2 | 2 |
| Ley 44/2015 | 5 | ok | boe | BOE-A-2015-11071 | 4 | 4 |
| OM 04/04/2000 | 5 | no-resuelta | — | — | 5 | 0 |
| RD 1299/2006 | 5 | ok | boe | BOE-A-2006-22169 | 1 | 1 |
| Convenio Protocolo Adicional al Convenio CMR | 4 | no-resuelta | — | — | 3 | 0 |
| Directiva 2003/59/CE | 4 | no-resuelta | — | — | 1 | 0 |
| Ley Orgánica 12/1995 | 4 | ok | boe | BOE-A-1995-26836 | 2 | 2 |
| OM 27/07/1999 | 4 | no-resuelta | — | — | 1 | 0 |
| OM INT/2223/2014 | 4 | ok | boe | BOE-A-2014-12411 | 2 | 2* |

`*` = además se guardó el texto completo de la norma (< 50 KB), que cubre cualquier referencia a ella.

## Normas del universo no resueltas

| Norma | Refs | Estado | Motivo |
| --- | ---: | --- | --- |
| Acuerdo ATP | 27 | no-resuelta | convenio/acuerdo/otros: fuera de alcance v1 |
| Convenio CMR | 25 | no-resuelta | convenio/acuerdo/otros: fuera de alcance v1 |
| Convenio CIDE | 11 | no-resuelta | convenio/acuerdo/otros: fuera de alcance v1 |
| Convenio TIR | 11 | no-resuelta | convenio/acuerdo/otros: fuera de alcance v1 |
| Convenio Aplicación del Acuerdo de Schengen | 8 | no-resuelta | convenio/acuerdo/otros: fuera de alcance v1 |
| Resolución D.G. Tráfico 01/06/2009 | 7 | no-resuelta | norma identificada por fecha, sin número oficial verificable |
| OM 04/04/2000 | 5 | no-resuelta | norma identificada por fecha, sin número oficial verificable |
| Convenio Protocolo Adicional al Convenio CMR | 4 | no-resuelta | convenio/acuerdo/otros: fuera de alcance v1 |
| Directiva 2003/59/CE | 4 | no-resuelta | directiva: fuera de alcance v1 |
| OM 27/07/1999 | 4 | no-resuelta | norma identificada por fecha, sin número oficial verificable |

## Cola larga (< 4 referencias, sin texto)

28 normas base, 38 referencias. No se intenta resolverlas en esta fase.

| Norma | Refs |
| --- | ---: |
| OM FOM/2861/2012 | 3 |
| Reglamento Comunitario (UE) 2015/2446 | 3 |
| Resolución Departamento de Aduanas e Impuestos Especiales 11/07/2014 | 3 |
| Acuerdo Adhesión de la República Portuguesa al Convenio de aplicación del Acuerdo de Schengen | 2 |
| RD 1345/2007 | 2 |
| RD 1407/1992 | 2 |
| RD 751/2006 | 2 |
| Acuerdo Adhesión de los reinos de España y Suecia y de la República Italiana al Convenio de aplicación del Acuerdo de Schengen | 1 |
| Acuerdo Adhesión del Reino de España al Convenio de aplicación del Acuerdo de Schengen;Acuerdos de la Unión Europea con la República de Islandia y el Reino de Noruega;y con la Confederación Suiza | 1 |
| Acuerdo Schengen | 1 |
| Convenio ATA | 1 |
| Convenio Protocolo de Adhesión a la Declaración Amistosa de Accidente | 1 |
| Directiva 2001/51/CE | 1 |
| Ley Código de Comercio | 1 |
| Ley Orgánica 10/1995 | 1 |
| Ley;RD 16/1987;1211/1990 | 1 |
| OM 21/07/2000 | 1 |
| OM FOM/3399/2002 | 1 |
| RD 2032/2009 | 1 |
| RD 487/1997 | 1 |
| RD Legislativo 6/2015 | 1 |
| Reglamento Comunitario (CE) 338/97 | 1 |
| Reglamento Comunitario (UE) 581/2010 | 1 |
| Reglamento Comunitario (UE) 952/2013;(UE) 2015/2446 | 1 |
| Reglamento Comunitario;RD (CE) 561/2006;640/2007 | 1 |
| Resolución Presidencia de la Agencia Estatal de Administración Tributaria 27/01/2009 Quinta | 1 |
| Resolución Presidencia de la Agencia Estatal de Administración Tributaria 27/01/2009 Sexta | 1 |
| Tratado Ámsterdam Protocolo por el que se integra el acervo de Schengen en el marco de la Unión Europea | 1 |
