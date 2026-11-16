DADOS = {
    "nome_select": "Leucemia Linfoblástica Aguda",
    "hospital": "Hospital Pequeno Príncipe",
    "titulo_diagnostico": "Leucemia Linfoblástica Aguda",
    "tipo_ilustracao": "leucemia_linfoblastica_aguda",
    # CID-10: C91.0 = Leucemia linfoblástica aguda [LLA]. Confirme com o serviço.
    "cid": "C91.0",
    # Preencha quando a equipe responsável revisar o texto. Enquanto "status" não for
    # "validado", o app gera apenas RASCUNHO (com marca d'água).
    "validacao": {
        "status": "pendente",          # trocar para "validado" após a revisão
        "revisado_por": "",            # ex.: "Dra. Fulana de Tal (Oncologia Pediátrica)"
        "data": "",                    # ex.: "16/11/2026"
        "versao": "",                  # ex.: "1.0"
    },
    # Cadastre aqui os protocolos/materiais oficiais em que o texto se baseia.
    # "autorizacao": "autorizada" (já pedimos e recebemos), "nao_se_aplica" (uso livre) ou "pendente".
    # Só as autorizadas / de uso livre são impressas no material.
    "referencias": [
        {
            "fonte": "A DEFINIR: protocolo de tratamento de LLA adotado pelo serviço",
            "entidade": "",
            "ano": "",
            "url": "",
            "autorizacao": "pendente",
        },
        {
            "fonte": "A DEFINIR: material educativo oficial para famílias (instituição de referência)",
            "entidade": "",
            "ano": "",
            "url": "",
            "autorizacao": "pendente",
        },
    ],
    "secoes": [
        {
            "icone": "gota",
            "titulo": "O que o(a) {nome} tem?",
            "cor": "#4A7FE0",
            "cor2": "#6FA0F5",
            "texto": (
                "A leucemia linfoblástica aguda é um câncer que começa na medula óssea, o tecido dentro dos ossos "
                "onde são produzidas as células do sangue. Nessa doença, algumas células muito jovens, chamadas "
                "linfoblastos, passam a se multiplicar de forma descontrolada e não amadurecem como deveriam.\n\n"
                "Essas células ocupam espaço na medula óssea e atrapalham a produção normal de glóbulos vermelhos, "
                "plaquetas e células de defesa. A doença não surgiu por algo que a família fez ou deixou de fazer "
                "e não é contagiosa."
            ),
        },
        {
            "icone": "estrela",
            "titulo": "O que isso pode fazer no corpo?",
            "cor": "#2FAE9E",
            "cor2": "#5FCBBD",
            "texto": (
                "A redução das células normais do sangue pode causar palidez, cansaço, febre ou infecções, além de "
                "manchas roxas e sangramentos com mais facilidade. Algumas crianças também apresentam dor nos ossos "
                "ou articulações, aumento dos gânglios, barriga aumentada ou perda de apetite.\n\n"
                "Nem toda criança apresenta os mesmos sinais. Exames de sangue, avaliação da medula óssea e outros "
                "exames ajudam a equipe a definir as características da doença e planejar o tratamento do(a) {nome}."
            ),
        },
        {
            "icone": "escudo",
            "titulo": "O caminho do tratamento",
            "cor": "#E0A233",
            "cor2": "#F0C169",
            "texto": (
                "O tratamento é feito em etapas e costuma durar muitos meses. A quimioterapia é a principal forma "
                "de tratamento e combina medicamentos em momentos diferentes. Também são administrados medicamentos "
                "para proteger e tratar o sistema nervoso central.\n"
                "• Dar os medicamentos exatamente como orientado e não interrompê-los por conta própria\n"
                "• Comparecer às consultas, exames e internações programadas\n"
                "• Seguir as orientações da equipe sobre alimentação, higiene e prevenção de infecções\n"
                "• Antes de oferecer outros remédios, vitaminas ou produtos naturais, conversar com a equipe"
            ),
        },
    ],
    "alerta_titulo": "Quando entrar em contato com a equipe com urgência",
    "alerta_itens": [
        "Febre: siga o valor de temperatura e a orientação de urgência fornecidos pela equipe de oncologia",
        "Dificuldade para respirar, sonolência incomum, desmaio, convulsão ou alteração importante do comportamento",
        "Sangramento que não para, sangue no vômito, urina ou fezes, ou aparecimento de muitas manchas roxas",
        "Vômitos repetidos, diarreia intensa ou dificuldade para beber líquidos e manter a hidratação",
        "Dor intensa ou piora importante do estado geral da criança",
    ],
    "rodape": (
        "Este material tem caráter informativo e não substitui as orientações individualizadas da equipe de oncologia. "
        "O tratamento e os cuidados podem variar conforme os exames e a fase do tratamento do(a) {nome}. "
        "Em caso de dúvida ou mudança no estado da criança, entre em contato com a equipe responsável."
    ),
}
