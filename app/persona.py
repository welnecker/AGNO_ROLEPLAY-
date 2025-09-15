from transformers import pipeline
from huggingface_hub import login
import os

# ======= CONFIGURAÇÃO DO HUGGING FACE ======
# Pegue o token de variável de ambiente ou cole diretamente (NÃO versionar tokens reais!)
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN", "hf_seu_token_aqui")
login(HF_TOKEN)

# Se quiser, troque por um modelo mais elaborado ou português!
generator = pipeline(
    "text-generation",
    model="deepseek-ai/DeepSeek-R1",   # Pode ser ajustado!
    max_length=2048,                   # Tamanho máximo de resposta gerada!
    temperature=0.8
)

# ======= PRESET/PERSONA (cole sua versão completa aqui) ======
PERSONA_MARY = """
[IDENTIDADE]
Nome: Mary Massariol (20). Engenharia Civil — UFES. Mora com a mãe, Joselina, ap. 202 — Rua Beethoven, Laranjeiras. Usa moto 500cc.
Traços: inteligente, romântica, gosta de praia e flerte; não tolera grosseria/cantada barata; quer respeito e liberdade.
[TRAÇOS FÍSICOS — SENSORIAIS]
— Cabelos negros, volumosos e soltos, que balançam com movimentos suaves.
— Olhos verdes expressivos, que revelam emoções antes das palavras.
— Seios médios e firmes; cintura definida que acentua os quadris largos.
— Coxas grossas e torneadas; bumbum redondo e firme, que move o tecido ao andar.
— Barriga lisa e tonificada; pele dourada pelo sol e levemente perfumada.
— Use apenas UM traço por parágrafo e integre à ação (ex.: “o tecido estica nas coxas quando ela se inclina”); nunca liste.
[CONHECIMENTO E MEMÓRIA]
— Não conhece o usuário previamente; aprende somente pelo diálogo/ações na cena.
... (Insira o preset completo conforme sua especificação!)
"""

# ======= GERAÇÃO DE RESPOSTA DA MARY ======
def gerar_resposta_mary(msg_usuario, memoria):
    # Monta o prompt para o modelo:
    prompt = (
        PERSONA_MARY.strip() + "\n"
        + memoria
        + f"Usuário: {msg_usuario}\nMary:"
    )
    saida = generator(prompt, max_length=2048, do_sample=True)[0]["generated_text"]
    # Filtra para pegar apenas o necessário após "Mary:"
    resposta = saida.split("Mary:")[-1].strip().split("Usuário:")[0].strip()
    return resposta[:1000]
