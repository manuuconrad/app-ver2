# MODELO PARA NOVAS DOENÇAS
# Copie este arquivo para um nome sem "__" no começo (ex.: anemia_falciforme.py).
# Arquivos que começam com "__" são ignorados pelo aplicativo.
#
# Use {nome} onde o nome da criança deve aparecer.
# Textos: linhas que começam com "• " viram lista. "\n\n" separa parágrafos.
# Ícones disponíveis: gota, estrela, escudo, coracao, pilula, balao, alerta.

DADOS = {
    "nome_select": "Nome da doença (como aparece na lista)",
    "hospital": "Nome do hospital / serviço",
    "titulo_diagnostico": "Nome da doença (como aparece no topo do material)",
    "cid": "",  # CID-10, ex.: "D57.1". Obrigatório para o conteúdo ser considerado validado.
    # "tipo_ilustracao": "anemia_falciforme",  # opcional (ver desenhar_ilustracao_dinamica no app.py)

    "validacao": {
        "status": "pendente",   # "validado" só depois da revisão da equipe responsável
        "revisado_por": "",
        "data": "",
        "versao": "",
    },
    "referencias": [
        {
            "fonte": "Título do protocolo / diretriz / material oficial",
            "entidade": "Instituição responsável",
            "ano": "",
            "url": "",
            "autorizacao": "pendente",  # "autorizada" | "nao_se_aplica" | "pendente"
        },
    ],

    "secoes": [
        {"icone": "gota", "titulo": "O que o(a) {nome} tem?", "cor": "#4A7FE0", "cor2": "#6FA0F5",
         "texto": "Texto baseado nas referências acima."},
        {"icone": "estrela", "titulo": "O que isso pode fazer no corpo?", "cor": "#2FAE9E", "cor2": "#5FCBBD",
         "texto": "Texto baseado nas referências acima."},
        {"icone": "escudo", "titulo": "O caminho do tratamento", "cor": "#E0A233", "cor2": "#F0C169",
         "texto": "Texto baseado nas referências acima.\n• Item de lista\n• Outro item"},
    ],
    "alerta_titulo": "Quando entrar em contato com a equipe com urgência",
    "alerta_itens": ["Sinal de alerta 1", "Sinal de alerta 2"],
    "rodape": (
        "Este material tem caráter informativo e não substitui as orientações individualizadas da equipe. "
        "Em caso de dúvida ou mudança no estado da criança, entre em contato com a equipe responsável."
    ),
}
