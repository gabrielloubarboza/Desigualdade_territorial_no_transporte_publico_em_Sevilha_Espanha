"""Traducción al portugués (Brasil) del informe para la versión PowerPoint.

Las claves son las cadenas exactas generadas por 18_informe_pdf.py y 17_figuras.py con los datos actuales
(lista completa en data/processed/textos_informe_es.json, `21_informe_pptx.py --coletar`). Nombres propios
(distritos, fuentes oficiales), números y códigos se mantienen. Un texto sin traducción se conserva y se informa.
"""
from __future__ import annotations

import re

TEXTOS: dict[str, str] = {
    # ---------------------------------------------------------------- cabeceras y portada
    "DESIGUALDAD TERRITORIAL EN LA OFERTA DE AUTOBUSES · SEVILLA": "DESIGUALDADE TERRITORIAL NA OFERTA DE ÔNIBUS · SEVILHA",
    "Fuentes: INE (Censo Anual de Población 2024, seccionado 2024) · IECA, malla de población 250 m 2024 (CC BY 4.0) · GTFS TUSSAM 20260928, Powered by MITRAMS · © OpenStreetMap contributors (ODbL). Día de referencia: miércoles 21/10/2026.":
        "Fontes: INE (Censo Anual de Población 2024, seções censitárias 2024) · IECA, grade de população 250 m 2024 (CC BY 4.0) · GTFS TUSSAM 20260928, Powered by MITRAMS · © OpenStreetMap contributors (ODbL). Dia de referência: quarta-feira 21/10/2026.",
    "SEVILLA · ANÁLISIS TERRITORIAL DEL TRANSPORTE PÚBLICO": "SEVILHA · ANÁLISE TERRITORIAL DO TRANSPORTE PÚBLICO",
    "Desigualdad territorial": "Desigualdade territorial",
    "en la oferta de autobuses": "na oferta de ônibus",
    "urbanos de Sevilla": "urbanos de Sevilha",
    "Densidad de población, accesibilidad peatonal y frecuencia programada del servicio TUSSAM":
        "Densidade populacional, acessibilidade a pé e frequência programada do serviço TUSSAM",
    "521 secciones censales · población INE a 01/01/2024": "521 seções censitárias · população INE em 01/01/2024",
    "GTFS TUSSAM 20260928 · día laborable 21/10/2026": "GTFS TUSSAM 20260928 · dia útil 21/10/2026",
    "Red peatonal OpenStreetMap · umbral de 400 m": "Rede de pedestres OpenStreetMap · limiar de 400 m",
    "Informe de portafolio · 2026": "Relatório de portfólio · 2026",
    "Mapa: red peatonal (OSM), paradas con salidas 07–09 (azul, tamaño según frecuencia)":
        "Mapa: rede de pedestres (OSM), paradas com partidas 07–09 (azul, tamanho conforme a frequência)",
    "y las 33 secciones prioritarias (blanco). © OpenStreetMap contributors, GTFS Powered by MITRAMS.":
        "e as 33 seções prioritárias (branco). © OpenStreetMap contributors, GTFS Powered by MITRAMS.",
    "Desigualdad territorial en la oferta de autobuses urbanos de Sevilla": "Desigualdade territorial na oferta de ônibus urbanos de Sevilha",
    # ---------------------------------------------------------------- títulos y antetítulos
    "PROBLEMA Y OBJETIVOS": "PROBLEMA E OBJETIVOS",
    "¿Dónde vive mucha gente con poco autobús?": "Onde vive muita gente com pouco ônibus?",
    "SEVILLA, 141 KM² Y 11 DISTRITOS": "SEVILHA, 141 KM² E 11 DISTRITOS",
    "Área de estudio y fuentes": "Área de estudo e fontes",
    "DENSIDAD OFICIAL POR SECCIÓN": "DENSIDADE OFICIAL POR SEÇÃO",
    "Distribución de la población": "Distribuição da população",
    "COBERTURA A 400 M POR LA RED": "COBERTURA A 400 M PELA REDE",
    "Accesibilidad peatonal a las paradas": "Acessibilidade a pé às paradas",
    "CUÁNTAS LÍNEAS DISTINTAS, NO CUÁNTAS PARADAS": "QUANTAS LINHAS DISTINTAS, NÃO QUANTAS PARADAS",
    "Diversidad de líneas accesibles": "Diversidade de linhas acessíveis",
    "SALIDAS ACCESIBLES POR HORA": "PARTIDAS ACESSÍVEIS POR HORA",
    "Frecuencia programada": "Frequência programada",
    "MAÑANA, MEDIODÍA Y TARDE": "MANHÃ, MEIO-DIA E TARDE",
    "Diferencias a lo largo del día": "Diferenças ao longo do dia",
    "UNA RELACIÓN DÉBIL": "UMA RELAÇÃO FRACA",
    "Densidad frente a oferta": "Densidade versus oferta",
    "UMBRALES Y TIPOLOGÍA A–D": "LIMIARES E TIPOLOGIA A–D",
    "Clasificación de las deficiencias": "Classificação das deficiências",
    "DÓNDE SE CONCENTRAN": "ONDE SE CONCENTRAM",
    "Las 33 secciones prioritarias": "As 33 seções prioritárias",
    "FALTA DE PARADA O POCA FRECUENCIA": "FALTA DE PARADA OU POUCA FREQUÊNCIA",
    "Las secciones de mayor prioridad": "As seções de maior prioridade",
    "QUÉ MUESTRA EL DIAGNÓSTICO": "O QUE O DIAGNÓSTICO MOSTRA",
    "Síntesis y limitaciones": "Síntese e limitações",
    # ---------------------------------------------------------------- página 1
    "Sevilla tiene una red de autobuses urbanos densa, pero la oferta no se reparte igual por la ciudad. Este informe localiza las <b>secciones censales con elevada densidad de población y una oferta de autobús relativamente insuficiente</b>, y explica en qué consiste esa insuficiencia en cada caso.":
        "Sevilha tem uma rede de ônibus urbanos densa, mas a oferta não se distribui igualmente pela cidade. Este relatório localiza as <b>seções censitárias com elevada densidade populacional e uma oferta de ônibus relativamente insuficiente</b> e explica em que consiste essa insuficiência em cada caso.",
    "<b>Pregunta central.</b> ¿Qué secciones censales de Sevilla combinan una elevada densidad de población con una oferta relativamente insuficiente de autobuses urbanos?":
        "<b>Pergunta central.</b> Quais seções censitárias de Sevilha combinam elevada densidade populacional com uma oferta relativamente insuficiente de ônibus urbanos?",
    "Tres dimensiones distintas de la oferta, medidas por separado:": "Três dimensões distintas da oferta, medidas separadamente:",
    "<b>Proximidad física</b>: ¿hay una parada con servicio a 400 m o menos de recorrido a pie por la red peatonal?":
        "<b>Proximidade física</b>: existe uma parada com serviço a 400 m ou menos de percurso a pé pela rede de pedestres?",
    "<b>Diversidad de líneas</b>: ¿cuántas líneas distintas se pueden tomar en esas paradas?":
        "<b>Diversidade de linhas</b>: quantas linhas distintas podem ser tomadas nessas paradas?",
    "<b>Frecuencia programada</b>: ¿cuántas salidas por hora ofrecen, sin contar dos veces el mismo autobús?":
        "<b>Frequência programada</b>: quantas partidas por hora elas oferecem, sem contar duas vezes o mesmo ônibus?",
    "Una sección puede tener paradas cercanas y, aun así, pocas líneas o salidas muy espaciadas. Por eso el diagnóstico distingue la falta de parada de la baja intensidad del servicio en paradas existentes.":
        "Uma seção pode ter paradas próximas e, ainda assim, poucas linhas ou partidas muito espaçadas. Por isso o diagnóstico distingue a falta de parada da baixa intensidade do serviço em paradas existentes.",
    "Alcance": "Escopo",
    "Autobús urbano de TUSSAM programado un miércoles laborable (21/10/2026), en tres franjas: 07–09, 12–14 y 17–19 h. No incluye metro, tranvía, Cercanías ni autobuses metropolitanos, ni mide la puntualidad real ni el acceso a destinos concretos.":
        "Ônibus urbano da TUSSAM programado em uma quarta-feira útil (21/10/2026), em três faixas: 07–09, 12–14 e 17–19 h. Não inclui metrô, bonde, Cercanías nem ônibus metropolitanos, nem mede a pontualidade real ou o acesso a destinos específicos.",
    "LA CIUDAD EN CIFRAS": "A CIDADE EM NÚMEROS",
    "habitantes (INE, 01/01/2024) en 521 secciones censales": "habitantes (INE, 01/01/2024) em 521 seções censitárias",
    "habitantes estimados por la malla IECA de 250 m, base de los cálculos de acceso": "habitantes estimados pela grade IECA de 250 m, base dos cálculos de acesso",
    "paradas de autobús con servicio el día de referencia": "paradas de ônibus com serviço no dia de referência",
    "viajes programados que circulan entre 07 y 09 h": "viagens programadas que circulam entre 07 e 09 h",
    "de la población estimada tiene parada a ≤ 400 m a pie": "da população estimada tem parada a ≤ 400 m a pé",
    "secciones densas con al menos una deficiencia relativa de oferta": "seções densas com pelo menos uma deficiência relativa de oferta",
    "La población oficial (INE) caracteriza las secciones; la estimada (IECA) mide el acceso.":
        "A população oficial (INE) caracteriza as seções; a estimada (IECA) mede o acesso.",
    "Son fuentes distintas y no se mezclan en un mismo indicador.": "São fontes distintas e não se misturam em um mesmo indicador.",
    # ---------------------------------------------------------------- página 2
    "Fuente": "Fonte", "Uso en el análisis": "Uso na análise", "Fecha": "Data",
    "INE · Censo Anual de Población": "INE · Censo Anual de Población",
    "Población oficial por sección (686.741 hab.)": "População oficial por seção (686.741 hab.)",
    "INE · Seccionado": "INE · Seções censitárias",
    "521 secciones, áreas y densidad (EPSG:25830)": "521 seções, áreas e densidade (EPSG:25830)",
    "IECA · Malla 250 m": "IECA · Grade 250 m",
    "Localización aproximada de residentes (887 celdas)": "Localização aproximada dos moradores (887 células)",
    "Paradas, líneas, viajes y horarios programados": "Paradas, linhas, viagens e horários programados",
    "versión 20260928": "versão 20260928",
    "Red peatonal, ríos, ferrocarriles y autovías": "Rede de pedestres, rios, ferrovias e autovias",
    "IDE Sevilla · capa TUSSAM": "IDE Sevilla · camada TUSSAM",
    "Solo control de calidad; no redistribuible": "Apenas controle de qualidade; não redistribuível",
    "Todo se proyecta en ETRS89 / UTM 30N (EPSG:25830). Los indicadores se calculan por sección censal con su geometría original; la malla del IECA solo sirve para situar a la población dentro de cada sección.":
        "Tudo é projetado em ETRS89 / UTM 30N (EPSG:25830). Os indicadores são calculados por seção censitária com sua geometria original; a grade do IECA serve apenas para situar a população dentro de cada seção.",
    "La población oficial de cada sección procede del INE. La malla del IECA (otra fuente, otro método) suma 684.251 habitantes dentro del municipio: se usa como denominador de la accesibilidad, nunca para sustituir la cifra oficial.":
        "A população oficial de cada seção vem do INE. A grade do IECA (outra fonte, outro método) soma 684.251 habitantes dentro do município: é usada como denominador da acessibilidade, nunca para substituir o número oficial.",
    "Cadena de procesamiento": "Cadeia de processamento",
    "PostgreSQL/PostGIS: carga de fuentes, secciones, malla y horarios GTFS.": "PostgreSQL/PostGIS: carga das fontes, seções, grade e horários GTFS.",
    "Python (OSMnx, NetworkX): red peatonal y recorridos hasta 400 m.": "Python (OSMnx, NetworkX): rede de pedestres e percursos de até 400 m.",
    "SQL: salidas por franja, deduplicación de viajes y agregación por sección.": "SQL: partidas por faixa, deduplicação de viagens e agregação por seção.",
    "Clasificación por umbrales explícitos y pruebas automáticas en cada etapa.": "Classificação por limiares explícitos e testes automáticos em cada etapa.",
    "Límite municipal y 521 secciones censales del seccionado INE a 01/01/2024, agrupadas en 11 distritos censales (código INE y denominación del distrito municipal). El municipio incluye un enclave al sur. Sin mapa base externo.":
        "Limite municipal e 521 seções censitárias do INE em 01/01/2024, agrupadas em 11 distritos censitários (código INE e nome do distrito municipal). O município inclui um enclave ao sul. Sem mapa base externo.",
    # ---------------------------------------------------------------- página 3
    "Las secciones de alta densidad se concentran en barrios residenciales de bloque: Macarena (29), Cerro-Amate (23), Triana (16), Norte (15), San Pablo-Santa Justa (15). El Casco Antiguo no tiene ninguna (0), y en la periferia las secciones extensas incluyen mucho suelo no residencial.":
        "As seções de alta densidade se concentram em bairros residenciais de prédios: Macarena (29), Cerro-Amate (23), Triana (16), Norte (15), San Pablo-Santa Justa (15). O Casco Antiguo não tem nenhuma (0), e na periferia as seções extensas incluem muito solo não residencial.",
    "La mitad de las secciones supera 20.652 hab./km². El cuartil superior empieza en <b>30.976,8 hab./km²</b>: ese es el umbral de <b>alta densidad</b> utilizado en la clasificación (131 secciones, 163.874 habitantes).":
        "Metade das seções supera 20.652 hab./km². O quartil superior começa em <b>30.976,8 hab./km²</b>: esse é o limiar de <b>alta densidade</b> usado na classificação (131 seções, 163.874 habitantes).",
    "Densidad no es lo mismo que población: entre las secciones de alta densidad, la menos poblada tiene 643 habitantes. La clasificación usa la densidad oficial (área total); una densidad sobre el área habitada se conserva como dato complementario.":
        "Densidade não é o mesmo que população: entre as seções de alta densidade, a menos populosa tem 643 habitantes. A classificação usa a densidade oficial (área total); uma densidade sobre a área habitada é mantida como dado complementar.",
    "Densidad = población INE 2024 / área total de la sección. Clases ancladas en los cuartiles municipales (P25, P50, P75).":
        "Densidade = população INE 2024 / área total da seção. Classes ancoradas nos quartis municipais (P25, P50, P75).",
    # ---------------------------------------------------------------- página 4
    "El 94,36 % de la población estimada tiene al menos una parada con servicio a 400 m o menos caminando. La carencia se concentra en bordes urbanos y en bolsas puntuales dentro de barrios densos.":
        "94,36 % da população estimada tem pelo menos uma parada com serviço a 400 m ou menos a pé. A carência se concentra nas bordas urbanas e em bolsões pontuais dentro de bairros densos.",
    "<b>645.680</b> habitantes cubiertos (94,36 %) · <b>38.379</b> sin parada a 400 m (5,61 %) · <b>192</b> no determinados (0,03 %; conexión a la red incierta).":
        "<b>645.680</b> habitantes cobertos (94,36 %) · <b>38.379</b> sem parada a 400 m (5,61 %) · <b>192</b> não determinados (0,03 %; ligação à rede incerta).",
    "Los 400 m son <b>recorrido por la red peatonal</b> de OpenStreetMap, no un círculo en línea recta: incluyen el acceso del punto de demanda a la calle y de la calle a la parada, y respetan ríos, vías de ferrocarril y autovías. El recorrido medio a la parada más cercana es de 209 m.":
        "Os 400 m são <b>percurso pela rede de pedestres</b> do OpenStreetMap, não um círculo em linha reta: incluem o acesso do ponto de demanda à rua e da rua à parada, e respeitam rios, ferrovias e autovias. O percurso médio até a parada mais próxima é de 209 m.",
    "La población se representa con 2.674 puntos (celda IECA × sección). No son domicilios: cada punto resume a los residentes estimados de su parcela.":
        "A população é representada por 2.674 pontos (célula IECA × seção). Não são domicílios: cada ponto resume os moradores estimados de sua parcela.",
    "Porcentaje de la población estimada (malla IECA) sin ninguna parada con servicio a ≤ 400 m de recorrido. Las secciones periféricas extensas destacan por superficie, pero concentran poca población.":
        "Percentual da população estimada (grade IECA) sem nenhuma parada com serviço a ≤ 400 m de percurso. As seções periféricas extensas se destacam pela área, mas concentram pouca população.",
    # ---------------------------------------------------------------- página 5
    "El residente medio puede tomar 3,55 líneas distintas a pie en la punta de la mañana (3,76 entre quienes tienen parada). Nervión, San Pablo y el entorno del Prado de San Sebastián superan las cinco líneas; muchos barrios dependen de una o dos.":
        "O morador médio pode tomar 3,55 linhas distintas a pé no pico da manhã (3,76 entre quem tem parada). Nervión, San Pablo e o entorno do Prado de San Sebastián superam cinco linhas; muitos bairros dependem de uma ou duas.",
    "Buena parte del Casco Antiguo, servido sobre todo por la circular C5 — que empieza después de las 10 h —, queda por debajo de una línea en esta franja.":
        "Boa parte do Casco Antiguo, atendido sobretudo pela circular C5 — que começa depois das 10 h —, fica abaixo de uma linha nesta faixa.",
    "El cuartil inferior se sitúa en <b>2,04 líneas</b>. Una línea cuenta una sola vez aunque pase por varias paradas cercanas.":
        "O quartil inferior fica em <b>2,04 linhas</b>. Uma linha conta uma única vez, mesmo que passe por várias paradas próximas.",
    "Ejemplos: secciones densas con una sola línea a su alcance (07–09)": "Exemplos: seções densas com uma única linha ao alcance (07–09)",
    "Sección": "Seção", "Distrito": "Distrito", "Líneas": "Linhas", "Salidas/h": "Partidas/h",
    "Líneas distintas con al menos una salida 07–09 en las paradas a ≤ 400 m, media ponderada por la población con parada. En gris, secciones sin población cubierta.":
        "Linhas distintas com pelo menos uma partida 07–09 nas paradas a ≤ 400 m, média ponderada pela população com parada. Em cinza, seções sem população coberta.",
    # ---------------------------------------------------------------- página 6
    "Entre las 7 y las 9 h, el residente medio tiene a su alcance 29,8 salidas por hora (31,6 entre quienes tienen parada). En el cuartil inferior hay 15,2 salidas/h o menos.":
        "Entre 7 e 9 h, o morador médio tem ao seu alcance 29,8 partidas por hora (31,6 entre quem tem parada). No quartil inferior há 15,2 partidas/h ou menos.",
    "Cómo se cuenta": "Como se conta",
    "Horarios del GTFS de TUSSAM para el servicio de días laborables (INVLAB40).": "Horários do GTFS da TUSSAM para o serviço de dias úteis (INVLAB40).",
    "<b>Sin duplicados</b>: un mismo viaje que pasa por tres paradas cercanas es una sola oportunidad de embarque. La deduplicación eliminó 230.199 pasos repetidos entre los tres periodos.":
        "<b>Sem duplicidade</b>: uma mesma viagem que passa por três paradas próximas é uma única oportunidade de embarque. A deduplicação eliminou 230.199 passagens repetidas nos três períodos.",
    "No se cuenta la última parada de cada viaje (solo bajada).": "A última parada de cada viagem não é contada (só desembarque).",
    "El 77 % de los horarios por parada se interpola entre puntos de control por distancia recorrida; un análisis de sensibilidad muestra que no altera las comparaciones.":
        "77 % dos horários por parada são interpolados entre pontos de controle pela distância percorrida; uma análise de sensibilidade mostra que isso não altera as comparações.",
    "Es la oferta accesible a un residente, no el número de autobuses que cruzan la sección.": "É a oferta acessível a um morador, não o número de ônibus que cruzam a seção.",
    "Viajes distintos con salida 07–09 en alguna parada a ≤ 400 m, divididos por 2 h; media ponderada por la población con parada.":
        "Viagens distintas com partida 07–09 em alguma parada a ≤ 400 m, divididas por 2 h; média ponderada pela população com parada.",
    # ---------------------------------------------------------------- página 7
    "La oferta accesible baja por la tarde: de 29,8 a 25,2 salidas/h para el residente medio (−15,5 %). El mediodía mantiene un nivel similar al de la mañana.":
        "A oferta acessível cai à tarde: de 29,8 para 25,2 partidas/h para o morador médio (−15,5 %). O meio-dia mantém um nível semelhante ao da manhã.",
    "Medias ponderadas por la población con accesibilidad determinada (sin parada = 0) y viajes de la red con al menos una salida en la franja.":
        "Médias ponderadas pela população com acessibilidade determinada (sem parada = 0) e viagens da rede com pelo menos uma partida na faixa.",
    "<b>475 de las 521 secciones</b> tienen menos salidas accesibles por la tarde (variación mediana −14,4 %; 72 pierden un 25 % o más). El número de líneas apenas cambia: la tarde no pierde líneas, pierde frecuencia.":
        "<b>475 das 521 seções</b> têm menos partidas acessíveis à tarde (variação mediana −14,4 %; 72 perdem 25 % ou mais). O número de linhas quase não muda: a tarde não perde linhas, perde frequência.",
    "La baja frecuencia de las áreas prioritarias es estructural: 22 de las 23 secciones prioritarias con baja frecuencia por la mañana la mantienen en las tres franjas.":
        "A baixa frequência das áreas prioritárias é estrutural: 22 das 23 seções prioritárias com baixa frequência pela manhã a mantêm nas três faixas.",
    "Las diferencias reflejan la programación del operador, no la demanda ni los viajeros transportados.":
        "As diferenças refletem a programação do operador, não a demanda nem os passageiros transportados.",
    "Variación porcentual de las salidas/h accesibles entre 17–19 y 07–09 por sección.": "Variação percentual das partidas/h acessíveis entre 17–19 e 07–09 por seção.",
    # ---------------------------------------------------------------- página 8
    "Cada punto es una sección censal. Línea discontinua vertical: umbral de alta densidad (P75). Líneas punteadas: cobertura media municipal y cuartil inferior de líneas y salidas. Correlación de Spearman (rangos, con empates promediados).":
        "Cada ponto é uma seção censitária. Linha tracejada vertical: limiar de alta densidade (P75). Linhas pontilhadas: cobertura média municipal e quartil inferior de linhas e partidas. Correlação de Spearman (postos, com empates pela média).",
    "Cuartil de densidad": "Quartil de densidade", "Con parada a 400 m": "Com parada a 400 m",
    "Salidas/h 07–09": "Partidas/h 07–09", "Sin parada (hab.)": "Sem parada (hab.)",
    "Más densidad se asocia con algo más de oferta, pero débilmente (Spearman: cobertura 0,37, líneas 0,16, salidas/h 0,18). La población sin parada se concentra en las secciones menos densas.":
        "Mais densidade se associa a um pouco mais de oferta, mas fracamente (Spearman: cobertura 0,37, linhas 0,16, partidas/h 0,18). A população sem parada se concentra nas seções menos densas.",
    "Dentro del grupo de alta densidad conviven secciones muy bien servidas y otras con una o dos líneas: es ahí donde se centra el diagnóstico. Una correlación no demuestra causalidad.":
        "Dentro do grupo de alta densidade convivem seções muito bem atendidas e outras com uma ou duas linhas: é aí que o diagnóstico se concentra. Uma correlação não demonstra causalidade.",
    # ---------------------------------------------------------------- página 9
    "Criterio": "Critério", "Regla (comparación interna a Sevilla)": "Regra (comparação interna a Sevilha)", "Umbral": "Limiar",
    "Alta densidad": "Alta densidade", "Cuartil superior de las 521 secciones": "Quartil superior das 521 seções",
    "Baja cobertura": "Baixa cobertura",
    "Por debajo de la cobertura municipal (el cuartil inferior es 100 %)": "Abaixo da cobertura municipal (o quartil inferior é 100 %)",
    "Pocas líneas": "Poucas linhas", "Cuartil inferior, población con parada, 07–09": "Quartil inferior, população com parada, 07–09",
    "Baja frecuencia": "Baixa frequência", "≤ 15,21 salidas/h": "≤ 15,21 partidas/h",
    "Tipología de las secciones de alta densidad": "Tipologia das seções de alta densidade",
    "<font color='#C8323F'><b>A · Baja cobertura</b></font>: parte relevante de los residentes sin parada a 400 m.":
        "<font color='#C8323F'><b>A · Baixa cobertura</b></font>: parte relevante dos moradores sem parada a 400 m.",
    "<font color='#E9A23B'><b>B · Pocas líneas</b></font>: paradas cercanas, pero pocas líneas disponibles.":
        "<font color='#E9A23B'><b>B · Poucas linhas</b></font>: paradas próximas, mas poucas linhas disponíveis.",
    "<font color='#21918C'><b>C · Baja frecuencia</b></font>: acceso y líneas suficientes, pocas salidas.":
        "<font color='#21918C'><b>C · Baixa frequência</b></font>: acesso e linhas suficientes, poucas partidas.",
    "<font color='#2B2D42'><b>D · Deficiencias combinadas</b></font>: más de una a la vez (en Sevilla, siempre pocas líneas y baja frecuencia).":
        "<font color='#2B2D42'><b>D · Deficiências combinadas</b></font>: mais de uma ao mesmo tempo (em Sevilha, sempre poucas linhas e baixa frequência).",
    "Precedencia: D si hay dos o más deficiencias; si no, A, B o C. Son <b>prioritarias</b> las secciones de alta densidad con al menos una deficiencia: <b>33 secciones y 41.208 habitantes</b> (6,0 % de la población oficial). Ninguna sección densa combina falta de parada con poca oferta.":
        "Precedência: D se há duas ou mais deficiências; caso contrário, A, B ou C. São <b>prioritárias</b> as seções de alta densidade com pelo menos uma deficiência: <b>33 seções e 41.208 habitantes</b> (6,0 % da população oficial). Nenhuma seção densa combina falta de parada com pouca oferta.",
    "Los umbrales son comparaciones dentro de la ciudad, no estándares técnicos ni legales de calidad.":
        "Os limiares são comparações dentro da cidade, não padrões técnicos nem legais de qualidade.",
    "Secciones y población INE por tipo.": "Seções e população INE por tipo.",
    "Secciones prioritarias por distrito censal y tipo; a la derecha, número de secciones y población INE.":
        "Seções prioritárias por distrito censitário e tipo; à direita, número de seções e população INE.",
    # ---------------------------------------------------------------- página 10
    "Tipología de cada sección (franja 07–09). Las prioritarias se resaltan con contorno; los números son las diez primeras del ranking. Códigos grises: distritos censales.":
        "Tipologia de cada seção (faixa 07–09). As prioritárias são destacadas com contorno; os números são as dez primeiras do ranking. Códigos cinza: distritos censitários.",
    "Las 33 secciones reúnen 41.208 residentes. Son piezas pequeñas (0,017–0,057 km²) dentro de barrios densos, no grandes vacíos de servicio.":
        "As 33 seções reúnem 41.208 moradores. São peças pequenas (0,017–0,057 km²) dentro de bairros densos, não grandes vazios de serviço.",
    "<b>Cerro-Amate (04)</b> concentra 7 secciones y el 21 % de la población prioritaria. Los casos de tipo A están en Los Remedios (3), Triana (1), Este-Alcosa-Torreblanca (1). Casco Antiguo y Bellavista-La Palmera no tienen secciones prioritarias.":
        "<b>Cerro-Amate (04)</b> concentra 7 seções e 21 % da população prioritária. Os casos do tipo A estão em Los Remedios (3), Triana (1), Este-Alcosa-Torreblanca (1). Casco Antiguo e Bellavista-La Palmera não têm seções prioritárias.",
    # ---------------------------------------------------------------- página 11
    "Dos situaciones distintas": "Duas situações distintas",
    "<b>Izquierda</b>: en Triana y Los Remedios hay paradas cerca, pero parte de los residentes (puntos rojos) quedan a más de 400 m de recorrido.":
        "<b>Esquerda</b>: em Triana e Los Remedios há paradas próximas, mas parte dos moradores (pontos vermelhos) fica a mais de 400 m de percurso.",
    "<b>Derecha</b>: en Cerro-Amate casi todos tienen parada, pero las paradas cercanas ofrecen una o dos líneas y pocas salidas (cuadrados pequeños).":
        "<b>Direita</b>: em Cerro-Amate quase todos têm parada, mas as paradas próximas oferecem uma ou duas linhas e poucas partidas (quadrados pequenos).",
    "La nº 1 depende de un único punto de demanda con 907 residentes estimados a 444 m de recorrido de la parada más cercana: un resultado próximo al umbral de 400 m, prioritario según la regla pero sensible a la localización del punto.":
        "A nº 1 depende de um único ponto de demanda com 907 moradores estimados a 444 m de percurso da parada mais próxima: um resultado próximo ao limiar de 400 m, prioritário segundo a regra, mas sensível à localização do ponto.",
    "El orden refleja criterios explícitos, no una medida universal de necesidad de inversión.":
        "A ordem reflete critérios explícitos, não uma medida universal de necessidade de investimento.",
    "Pob. INE": "Pop. INE", "Con parada": "Com parada", "Líneas*": "Linhas*", "Salidas/h*": "Partidas/h*",
    "Motivo principal": "Motivo principal",
    "907 hab. sin parada": "907 hab. sem parada", "346 hab. sin parada": "346 hab. sem parada",
    "105 hab. sin parada": "105 hab. sem parada", "91 hab. sin parada": "91 hab. sem parada", "53 hab. sin parada": "53 hab. sem parada",
    "1,5 líneas, 7,1 salidas/h": "1,5 linhas, 7,1 partidas/h", "1,0 líneas, 4,6 salidas/h": "1,0 linhas, 4,6 partidas/h",
    "1,0 líneas, 5,5 salidas/h": "1,0 linhas, 5,5 partidas/h", "1,0 líneas, 6,4 salidas/h": "1,0 linhas, 6,4 partidas/h",
    "1,5 líneas, 8,2 salidas/h": "1,5 linhas, 8,2 partidas/h",
    "* Media entre la población con parada, 07–09. Orden: dimensiones deficientes (acceso, servicio) → población sin oferta → menor frecuencia → menos líneas → mayor densidad → código.":
        "* Média entre a população com parada, 07–09. Ordem: dimensões deficientes (acesso, serviço) → população sem oferta → menor frequência → menos linhas → maior densidade → código.",
    # ---------------------------------------------------------------- página 12
    "Conclusiones": "Conclusões",
    "La cobertura física es alta (94,36 %): la desigualdad está más en <b>cuántas líneas y salidas</b> hay en las paradas cercanas que en la existencia de una parada.":
        "A cobertura física é alta (94,36 %): a desigualdade está mais em <b>quantas linhas e partidas</b> há nas paradas próximas do que na existência de uma parada.",
    "33 secciones densas (41.208 residentes, 6,0 %) combinan alta densidad con al menos una deficiencia relativa; 18 de ellas tienen a la vez pocas líneas y baja frecuencia.":
        "33 seções densas (41.208 moradores, 6,0 %) combinam alta densidade com pelo menos uma deficiência relativa; 18 delas têm ao mesmo tempo poucas linhas e baixa frequência.",
    "Los casos de falta de parada (tipo A) se agrupan en Los Remedios y Triana; los de servicio débil (B, C, D) se reparten por Cerro-Amate, Triana, Norte, Este-Alcosa-Torreblanca, San Pablo-Santa Justa, Macarena, Sur.":
        "Os casos de falta de parada (tipo A) se agrupam em Los Remedios e Triana; os de serviço fraco (B, C, D) se distribuem por Cerro-Amate, Triana, Norte, Este-Alcosa-Torreblanca, San Pablo-Santa Justa, Macarena, Sur.",
    "La tarde ofrece un 15 % menos de salidas accesibles que la mañana; la baja frecuencia de las prioritarias se mantiene durante todo el día.":
        "A tarde oferece 15 % menos partidas acessíveis que a manhã; a baixa frequência das prioritárias se mantém durante todo o dia.",
    "Con tercios en lugar de cuartiles hay 58 prioritarias y las 33 originales siguen en el grupo: el resultado es estable ante ese cambio, aunque depende de otras decisiones metodológicas.":
        "Com tercis em vez de quartis há 58 prioritárias e as 33 originais continuam no grupo: o resultado é estável diante dessa mudança, embora dependa de outras decisões metodológicas.",
    "Hay secciones con deficiencias graves y densidad intermedia (p. ej., 4109106007) fuera de las 33: el modelo no identifica todas las áreas que podrían necesitar mejoras.":
        "Há seções com deficiências graves e densidade intermediária (p. ex., 4109106007) fora das 33: o modelo não identifica todas as áreas que poderiam precisar de melhorias.",
    "Uso del diagnóstico": "Uso do diagnóstico",
    "Señala dónde mirar primero y por qué (acceso o servicio). La prioridad territorial no equivale a una recomendación de intervención: no se han simulado nuevas líneas ni paradas.":
        "Indica onde olhar primeiro e por quê (acesso ou serviço). A prioridade territorial não equivale a uma recomendação de intervenção: não foram simuladas novas linhas nem paradas.",
    "Limitaciones": "Limitações",
    "<b>Oferta programada</b> en el GTFS, no servicio realizado ni puntualidad.": "<b>Oferta programada</b> no GTFS, não serviço realizado nem pontualidade.",
    "<b>Horarios interpolados</b>: ~77 % de los horarios por parada; la sensibilidad (±2 min) cambia la frecuencia media menos de un 0,5 %.":
        "<b>Horários interpolados</b>: ~77 % dos horários por parada; a sensibilidade (±2 min) altera a frequência média em menos de 0,5 %.",
    "<b>Población aproximada</b> por la malla IECA para el acceso; difiere de la cifra INE en cada sección.":
        "<b>População aproximada</b> pela grade IECA para o acesso; difere do número do INE em cada seção.",
    "<b>Umbral rígido de 400 m</b>: en 3 prioritarias, más de la mitad de la población está a 350–450 m.":
        "<b>Limiar rígido de 400 m</b>: em 3 prioritárias, mais da metade da população está a 350–450 m.",
    "<b>Umbrales relativos</b> (cuartiles, media municipal), internos a Sevilla.": "<b>Limiares relativos</b> (quartis, média municipal), internos a Sevilha.",
    "<b>Solo autobús urbano TUSSAM</b>: sin metro, tranvía, Cercanías ni autobuses metropolitanos.":
        "<b>Apenas ônibus urbano TUSSAM</b>: sem metrô, bonde, Cercanías nem ônibus metropolitanos.",
    "<b>Red OSM</b> sin aceras explícitas; las autovías sin paso peatonal se excluyen por prudencia.":
        "<b>Rede OSM</b> sem calçadas explícitas; as autovias sem passagem de pedestres são excluídas por precaução.",
    "Densidad sobre el <b>área total</b> de la sección; algunas secciones con suelo no residencial quedan por debajo del umbral.":
        "Densidade sobre a <b>área total</b> da seção; algumas seções com solo não residencial ficam abaixo do limiar.",
    "Código, datos derivados y metodología: repositorio del proyecto (README, docs/ y produtos/).":
        "Código, dados derivados e metodologia: repositório do projeto (README, docs/ e produtos/).",
}

FIGURAS: dict[str, str] = {
    "0,03 % no determinada": "0,03 % não determinada",
    "5,61 % sin parada": "5,61 % sem parada",
    "94,36 % con parada": "94,36 % com parada",
    "A · Baja cobertura peatonal": "A · Baixa cobertura a pé",
    "A · Baja cobertura peatonal (5)": "A · Baixa cobertura a pé (5)",
    "B · Pocas líneas": "B · Poucas linhas", "B · Pocas líneas (5)": "B · Poucas linhas (5)",
    "C · Baja frecuencia": "C · Baixa frequência", "C · Baja frecuencia (5)": "C · Baixa frequência (5)",
    "D · Deficiencias combinadas": "D · Deficiências combinadas", "D · Deficiencias combinadas (18)": "D · Deficiências combinadas (18)",
    "Alta densidad sin deficiencia (98)": "Alta densidade sem deficiência (98)",
    "Fuera de alta densidad (390)": "Fora da alta densidade (390)",
    "Andalucía": "Andaluzia",
    "Cerro-Amate — parada cercana con pocas salidas": "Cerro-Amate — parada próxima com poucas partidas",
    "Triana y Los Remedios — falta de parada cercana": "Triana e Los Remedios — falta de parada próxima",
    "Clasificación (franja 07–09)": "Classificação (faixa 07–09)",
    "Densidad (miles de hab./km²)": "Densidade (mil hab./km²)",
    "Densidad (miles hab./km²)": "Densidade (mil hab./km²)",
    "Las 33 secciones prioritarias por orden de ranking\n(tamaño = población estimada sin oferta a 07–09)":
        "As 33 seções prioritárias por ordem de ranking\n(tamanho = população estimada sem oferta às 07–09)",
    "Líneas accesibles\n(residente medio)": "Linhas acessíveis\n(morador médio)",
    "Líneas accesibles 07–09 (con parada)\nSpearman = 0,16": "Linhas acessíveis 07–09 (com parada)\nSpearman = 0,16",
    "Líneas distintas accesibles (07–09) — población con parada": "Linhas distintas acessíveis (07–09) — população com parada",
    "Líneas distintas accesibles, 07–09\n(media entre la población con parada)": "Linhas distintas acessíveis, 07–09\n(média entre a população com parada)",
    "P75 = 30.977\nalta densidad": "P75 = 30.977\nalta densidade",
    "Parada (tamaño = salidas/h 07–09)": "Parada (tamanho = partidas/h 07–09)",
    "Población INE 2024": "População INE 2024",
    "Población con parada a ≤ 400 m (%)\nSpearman = 0,37": "População com parada a ≤ 400 m (%)\nSpearman = 0,37",
    "Población estimada sin parada\na ≤ 400 m de recorrido (%)": "População estimada sem parada\na ≤ 400 m de percurso (%)",
    "Punto de demanda con parada a ≤ 400 m": "Ponto de demanda com parada a ≤ 400 m",
    "Punto sin parada a ≤ 400 m": "Ponto sem parada a ≤ 400 m",
    "Red peatonal": "Rede de pedestres",
    "Resto de secciones": "Demais seções",
    "Río Guadalquivir": "Rio Guadalquivir",
    "Salidas programadas accesibles por hora, 07–09\n(viajes sin duplicar; población con parada)":
        "Partidas programadas acessíveis por hora, 07–09\n(viagens sem duplicidade; população com parada)",
    "Salidas/h accesibles\n(residente medio)": "Partidas/h acessíveis\n(morador médio)",
    "Salidas/h accesibles (07–09) — población con parada": "Partidas/h acessíveis (07–09) — população com parada",
    "Salidas/h accesibles 07–09 (con parada)\nSpearman = 0,18": "Partidas/h acessíveis 07–09 (com parada)\nSpearman = 0,18",
    "Salidas/h accesibles 07–09 (residente medio; sin parada = 0)": "Partidas/h acessíveis 07–09 (morador médio; sem parada = 0)",
    "Secciones": "Seções",
    "Secciones prioritarias por distrito y tipo": "Seções prioritárias por distrito e tipo",
    "Sin población con parada": "Sem população com parada",
    "Sin salidas por la mañana": "Sem partidas pela manhã",
    "Variación de las salidas/h accesibles\ntarde (17–19) frente a mañana (07–09)": "Variação das partidas/h acessíveis\ntarde (17–19) versus manhã (07–09)",
    "Viajes en la red\n(≥ 1 salida en la franja)": "Viagens na rede\n(≥ 1 partida na faixa)",
    "media municipal": "média municipal",
    "0 % (cobertura total)": "0 % (cobertura total)",
    "Habitantes/km² (INE 2024)": "Habitantes/km² (INE 2024)",
}

# Fragmentos que no se traducen (nombres propios, siglas, unidades, cuartiles, códigos)
_NEUTROS = ["Casco Antiguo", "Macarena", "Nervión", "Cerro-Amate", "Sur", "Triana", "Norte", "San Pablo-Santa Justa",
            "Este-Alcosa-Torreblanca", "Bellavista-La Palmera", "Los Remedios", "OpenStreetMap", "TUSSAM", "GTFS", "NAP",
            "MITRAMS", "Tipo", "Spearman", "Easting [metre]", "Northing [metre]", "hab.", "km²", "km", "Hab./km²",
            "P25", "P50", "P75", "Q1", "Q2", "Q3", "Q4", "1e6"]


def _neutro(s: str) -> bool:
    t = s
    for n in sorted(_NEUTROS, key=len, reverse=True):
        t = t.replace(n, "")
    t = re.sub(r"(?<=\d)\s+a\s+(?=[+−\-]?\d)", " ", t)   # "−10 a +10 %"
    return not re.search(r"[A-Za-zÀ-ÿ]{2,}", t)


class Tradutor:
    def __init__(self, lang: str, coletar: bool = False):
        self.lang, self.coletar = lang, coletar
        self.vistos: list[str] = []
        self.faltantes: set[str] = set()

    def _t(self, s, dic):
        if self.coletar and isinstance(s, str):
            self.vistos.append(s)
        if self.lang == "es" or not isinstance(s, str) or not s.strip():
            return s
        if s in dic:
            return dic[s]
        if s in dic.values() or len(s.strip()) == 1 or _neutro(s):
            return s
        self.faltantes.add(s)
        return s

    def __call__(self, s):
        return self._t(s, TEXTOS)

    def fig(self, s):
        return self._t(s, FIGURAS)
