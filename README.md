# Stealth Login Flow

Automacao de login com `stealth-browser-mcp`, usando configuracao por arquivos separados em `env/`, logs de rastreio e screenshots em `artifacts`.

## 1. Preparacao

```bash
cp .env.example .env
cp env/runtime.env.example env/runtime.env
cp env/credentials.env.example env/credentials.env
cp env/selectors.env.example env/selectors.env
cp env/validation.env.example env/validation.env
cp env/timeouts.env.example env/timeouts.env
# ajuste os valores nos arquivos env/*.env
./install_stealth_browser.sh
```

Se ja existir um `.env` unico antigo, migre automaticamente:

```bash
python3 migrate_env_split.py --source .env --backup --write-orchestrator
```

## 2. Execucao

Interface de programa (desktop):

```bash
python3 stealth_login_ui.py
```

Na UI, marque `Retomar sessao (dashboard)` para reabrir com sessao salva (perfil em `USER_DATA_DIR`), revalidar o `STEP5_VALIDATION_TEXT` e continuar dali.
Se sua app redirecionar para outro path, ajuste `DASHBOARD_PATH_FRAGMENT` em `env/runtime.env`.

Modo visivel (`headed`):

```bash
python3 stealth_login_flow.py --headed
```

Modo background com navegador `headed` (recomendado para captcha invisivel):

```bash
python3 stealth_login_flow.py --background-headed
```

Retomada de sessao direto no dashboard:

```bash
python3 stealth_login_flow.py --background-headed --resume-session
```

Por padrao o navegador fica aberto ao final. Para fechar ao concluir o fluxo:

```bash
python3 stealth_login_flow.py --no-keep-open
```

Se quiser trocar a pilha de arquivos de configuracao, use `ENV_FILES`:

```bash
ENV_FILES=\"env/runtime.env,env/credentials.env,env/selectors.env,env/validation.env,env/timeouts.env\" python3 stealth_login_flow.py --background-headed
```

## Observacoes

- O script loga os passos com sanitizacao (sem exibir URLs).
- Antes e depois do click em `ENTRAR`, salva screenshots em `artifacts/`.
- Apos validar o pos-login, clica no botao `Receber código por EMAIL` (configuravel em `env/selectors.env`), salva nova screenshot e pode validar texto dessa etapa.
- Apos validar a etapa de envio do codigo, o script solicita o codigo OTP no console, preenche o campo e clica em `AUTENTICAR`.
- `--background-headed` relanca o processo com `xvfb-run` para manter o navegador em modo headed sem janela visivel.
- Na UI desktop, apos OTP confirmado no `background-headed`, o menu `Baixar Boletos` permite escolher uma pasta, executar o fluxo de filtros e baixar todos os links `BAIXAR BOLETO` da lista (um a um) para o diretorio selecionado.
- Na UI desktop, voce pode retomar sessao salva pelo dashboard sem refazer login/OTP marcando `Retomar sessao (dashboard)` (revalidando `STEP5_VALIDATION_TEXT`).
- Validacoes de texto por pagina sao configuradas em `env/validation.env`.
- A validacao de texto do `STEP-5` (apos autenticar OTP) usa `STEP5_VALIDATION_TEXT` em `env/validation.env` (ou `POST_AUTH_VALIDATION_TEXT` para compatibilidade).
- Em Linux/container, mantenha `BROWSER_SANDBOX=false` para evitar falha ao iniciar o Chrome.
- Para `--background-headed`, instale `xvfb`: `sudo apt-get update && sudo apt-get install -y xvfb`.
# stealth-alelo
