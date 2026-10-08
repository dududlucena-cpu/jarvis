"""
JARVIS - assistente de voz pessoal em Python

Recursos:
  - Ouve pelo microfone (diga "Jarvis" antes do comando) ou usa modo texto
  - Responde em voz alta (TTS offline)
  - Comandos locais: horas, data, abrir sites, pesquisar no Google
  - Conversa com Claude via API da Anthropic

Instalação:
  pip install anthropic SpeechRecognition pyttsx3 pyaudio

Chave de API:
  export ANTHROPIC_API_KEY="sua-chave"     (Linux/macOS)
  set ANTHROPIC_API_KEY=sua-chave          (Windows)

Execução:
  python jarvis.py            -> modo voz
  python jarvis.py --texto    -> modo digitado
"""

import datetime
import os
import sys
import urllib.parse
import webbrowser

import anthropic
import pyttsx3

try:
    import speech_recognition as sr
except ImportError:
    sr = None


# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------
MODELO = "claude-haiku-5-5"  # rápido; troque por "claude-sonnet-5-5" para respostas mais elaboradas
PALAVRA_DE_ATIVACAO = "jarvis"
MAX_MENSAGENS = 10           # tamanho da memória de curto prazo da conversa

PROMPT_SISTEMA = (
    "Você é JARVIS, um assistente pessoal inteligente, prestativo e com um toque "
    "de humor britânico, inspirado no assistente do Tony Stark. Responda sempre em "
    "português do Brasil, de forma curta e natural, pois a resposta será falada em "
    "voz alta. Não use listas, markdown ou emojis."
)

SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
}


# ---------------------------------------------------------------------------
# Voz (saída)
# ---------------------------------------------------------------------------
class Voz:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 175)
        for voz in self.engine.getProperty("voices"):
            info = f"{voz.name} {voz.id}".lower()
            if "brazil" in info or "portugu" in info or "pt-br" in info or "pt_br" in info:
                self.engine.setProperty("voice", voz.id)
                break

    def falar(self, texto):
        print(f"JARVIS: {texto}")
        self.engine.say(texto)
        self.engine.runAndWait()


# ---------------------------------------------------------------------------
# Ouvido (entrada por microfone)
# ---------------------------------------------------------------------------
class Ouvido:
    def __init__(self):
        if sr is None:
            raise RuntimeError("biblioteca SpeechRecognition não instalada")
        self.reconhecedor = sr.Recognizer()
        self.microfone = sr.Microphone()
        with self.microfone as fonte:
            self.reconhecedor.adjust_for_ambient_noise(fonte, duration=1)

    def ouvir(self):
        with self.microfone as fonte:
            try:
                audio = self.reconhecedor.listen(fonte, timeout=5, phrase_time_limit=12)
                return self.reconhecedor.recognize_google(audio, language="pt-BR").lower()
            except sr.WaitTimeoutError:
                return ""
            except sr.UnknownValueError:
                return ""
            except sr.RequestError:
                print("Não consegui acessar o serviço de reconhecimento de voz.")
                return ""


# ---------------------------------------------------------------------------
# Cérebro (conversa com Claude)
# ---------------------------------------------------------------------------
class Cerebro:
    def __init__(self):
        self.cliente = anthropic.Anthropic()
        self.historico = []

    def responder(self, pergunta):
        self.historico.append({"role": "user", "content": pergunta})
        try:
            resposta = self.cliente.messages.create(
                model=MODELO,
                max_tokens=400,
                system=PROMPT_SISTEMA,
                messages=self.historico,
            )
        except anthropic.APIError as erro:
            print(f"[erro na API] {erro}")
            self.historico.pop()
            return "Peço desculpas. Não consegui falar com o servidor agora."

        texto = "".join(b.text for b in resposta.content if b.type == "text").strip()
        self.historico.append({"role": "assistant", "content": texto})
        # Mantém número par de mensagens para a conversa sempre começar com "user"
        self.historico = self.historico[-MAX_MENSAGENS:]
        return texto


# ---------------------------------------------------------------------------
# Comandos locais (sem usar a IA)
# ---------------------------------------------------------------------------
def comando_local(texto):
    """Executa comandos simples. Retorna a resposta falada ou None."""
    agora = datetime.datetime.now()

    if "que horas" in texto or "hora é" in texto:
        return f"Agora são {agora:%H:%M}."

    if "que dia" in texto or "data de hoje" in texto:
        return f"Hoje é {agora:%d/%m/%Y}."

    if texto.startswith(("abrir ", "abra ", "abre ")):
        for nome, url in SITES.items():
            if nome in texto:
                webbrowser.open(url)
                return f"Abrindo {nome}."

    for gatilho in ("pesquisar por ", "pesquise por ", "pesquisar ", "pesquise "):
        if texto.startswith(gatilho):
            termo = texto[len(gatilho):]
            url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(termo)
            webbrowser.open(url)
            return f"Pesquisando {termo} no Google."

    return None


def extrair_comando(fala):
    """Só aceita falas que começam com a palavra de ativação.
    Retorna o comando (pode ser vazio) ou None se não for para o Jarvis."""
    fala = fala.strip().lower()
    if not fala.startswith(PALAVRA_DE_ATIVACAO):
        return None
    return fala[len(PALAVRA_DE_ATIVACAO):].strip(" ,.!?")


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------
def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Defina a variável de ambiente ANTHROPIC_API_KEY antes de iniciar.")
        sys.exit(1)

    modo_texto = "--texto" in sys.argv
    ouvido = None
    if not modo_texto:
        try:
            ouvido = Ouvido()
        except Exception as erro:
            print(f"Microfone indisponível ({erro}). Mudando para modo texto.")
            modo_texto = True

    voz = Voz()
    cerebro = Cerebro()
    voz.falar("Sistemas online. Em que posso ajudar?")

    if not modo_texto:
        print(f"Ouvindo... diga '{PALAVRA_DE_ATIVACAO}' seguido do comando. Para sair: 'Jarvis, sair'.")

    while True:
        if modo_texto:
            comando = input("Você: ").strip().lower()
            if not comando:
                continue
        else:
            fala = ouvido.ouvir()
            if not fala:
                continue
            comando = extrair_comando(fala)
            if comando is None:
                continue
            if not comando:
                voz.falar("Pois não?")
                continue
            print(f"Você: {comando}")

        if comando in ("sair", "encerrar", "tchau", "desligar"):
            voz.falar("Até logo.")
            break

        resposta = comando_local(comando) or cerebro.responder(comando)
        voz.falar(resposta)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nJARVIS desligado.")