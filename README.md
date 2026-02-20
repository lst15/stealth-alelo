# Stealth Login Flow

Automacao de login com `stealth-browser-mcp`, usando configuracao em `.env`, logs de rastreio e screenshots em `artifacts`.

## 1. Preparacao

```bash
cp .env.example .env
# ajuste os valores no .env
./install_stealth_browser.sh
```

## 2. Execucao

Modo visivel (`headed`):

```bash
python3 stealth_login_flow.py --headed
```

Modo background (`headless`):

```bash
python3 stealth_login_flow.py --headless
```

Modo background com navegador `headed` (recomendado para captcha invisivel):

```bash
python3 stealth_login_flow.py --background-headed
```

Por padrao o navegador fica aberto ao final. Para fechar ao concluir o fluxo:

```bash
python3 stealth_login_flow.py --no-keep-open
```

## Observacoes

- O script loga os passos e a URL final do redirect.
- Antes e depois do click em `ENTRAR`, salva screenshots em `artifacts/`.
- Apos validar o pos-login, clica no botao `Receber código por EMAIL` (configuravel no `.env`), salva nova screenshot e pode validar texto dessa etapa.
- Em `--headless`, apos validar a etapa de envio do codigo, o script solicita o codigo OTP no console, preenche o campo e clica em `AUTENTICAR`.
- `--background-headed` relanca o processo com `xvfb-run` para manter o navegador em modo headed sem janela visivel.
- Validacoes de texto por pagina sao configuradas por `REDIRECT_VALIDATION_TEXT` e `POST_LOGIN_VALIDATION_TEXT` no `.env`.
- A validacao de texto do `STEP-5` (apos autenticar OTP) usa `STEP5_VALIDATION_TEXT` no `.env` (ou `POST_AUTH_VALIDATION_TEXT` para compatibilidade).
- Em Linux/container, mantenha `BROWSER_SANDBOX=false` para evitar falha ao iniciar o Chrome.
- Para `--background-headed`, instale `xvfb`: `sudo apt-get update && sudo apt-get install -y xvfb`.
# stealth-alelo
