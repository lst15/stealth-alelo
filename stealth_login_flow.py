#!/usr/bin/env python3
import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any


def log(step: str, message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{step}] {message}", flush=True)


def parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def load_dotenv_file(path: Path) -> Dict[str, str]:
    env = {}
    if not path.exists():
        return env

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value and value[0] == value[-1] and value[0] in {"\"", "'"}:
            value = value[1:-1]

        env[key] = value

    return env


def get_env(env: Dict[str, str], key: str, default: Optional[str] = None) -> Optional[str]:
    if key in os.environ:
        return os.environ[key]
    return env.get(key, default)


@dataclass
class Config:
    stealth_path: Path
    login_url: str
    redirect_validation_text: str
    post_login_validation_text: str
    cpf: str
    senha: str
    cpf_selector: str
    senha_selector: str
    entrar_selector: str
    entrar_text: str
    receive_code_selector: str
    receive_code_text: str
    receive_code_validation_text: str
    otp_input_selector: str
    authenticate_button_selector: str
    authenticate_button_text: str
    post_auth_validation_text: str
    headless: bool
    sandbox: bool
    keep_browser_open: bool
    redirect_timeout_seconds: int
    post_login_timeout_seconds: int
    receive_code_timeout_seconds: int
    post_auth_timeout_seconds: int
    poll_interval_seconds: float


def build_config(args: argparse.Namespace) -> Config:
    dotenv = load_dotenv_file(Path(".env"))

    login_url = get_env(dotenv, "LOGIN_URL")
    cpf = get_env(dotenv, "CPF")
    senha = get_env(dotenv, "SENHA")

    missing = [
        name
        for name, value in {
            "LOGIN_URL": login_url,
            "CPF": cpf,
            "SENHA": senha,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Variaveis obrigatorias ausentes no .env: {', '.join(missing)}")

    headless_from_env = parse_bool(get_env(dotenv, "HEADLESS"), default=False)
    if args.headed:
        headless = False
    elif args.headless:
        headless = True
    else:
        headless = headless_from_env

    keep_open = parse_bool(get_env(dotenv, "KEEP_BROWSER_OPEN"), default=True)
    if args.no_keep_open:
        keep_open = False

    stealth_path = Path(get_env(dotenv, "STEALTH_BROWSER_MCP_PATH", ".stealth-browser-mcp")).resolve()

    return Config(
        stealth_path=stealth_path,
        login_url=login_url,
        redirect_validation_text=get_env(dotenv, "REDIRECT_VALIDATION_TEXT", "").strip(),
        post_login_validation_text=get_env(dotenv, "POST_LOGIN_VALIDATION_TEXT", "").strip(),
        cpf=cpf,
        senha=senha,
        cpf_selector=get_env(
            dotenv,
            "CPF_SELECTOR",
            'input[name="cpf"], input[id*="cpf" i], input[placeholder*="CPF" i]'
        ),
        senha_selector=get_env(
            dotenv,
            "SENHA_SELECTOR",
            'input[type="password"], input[name*="senha" i], input[id*="senha" i]'
        ),
        entrar_selector=get_env(
            dotenv,
            "ENTRAR_BUTTON_SELECTOR",
            'button, input[type="submit"], a'
        ),
        entrar_text=get_env(dotenv, "ENTRAR_BUTTON_TEXT", "ENTRAR"),
        receive_code_selector=get_env(
            dotenv,
            "RECEIVE_CODE_BUTTON_SELECTOR",
            'button, input[type="button"], input[type="submit"], a'
        ),
        receive_code_text=get_env(dotenv, "RECEIVE_CODE_BUTTON_TEXT", "Receber código por EMAIL"),
        receive_code_validation_text=get_env(dotenv, "RECEIVE_CODE_VALIDATION_TEXT", "").strip(),
        otp_input_selector=get_env(
            dotenv,
            "OTP_INPUT_SELECTOR",
            'input[placeholder*="Digite o código" i], input[name*="codigo" i], input[id*="codigo" i], input[type="text"]',
        ),
        authenticate_button_selector=get_env(
            dotenv,
            "AUTHENTICATE_BUTTON_SELECTOR",
            'button, input[type="button"], input[type="submit"], a',
        ),
        authenticate_button_text=get_env(dotenv, "AUTHENTICATE_BUTTON_TEXT", "AUTENTICAR"),
        post_auth_validation_text=get_env(dotenv, "POST_AUTH_VALIDATION_TEXT", "").strip(),
        headless=headless,
        sandbox=parse_bool(get_env(dotenv, "BROWSER_SANDBOX"), default=False),
        keep_browser_open=keep_open,
        redirect_timeout_seconds=int(get_env(dotenv, "REDIRECT_TIMEOUT_SECONDS", "60")),
        post_login_timeout_seconds=int(get_env(dotenv, "POST_LOGIN_TIMEOUT_SECONDS", "60")),
        receive_code_timeout_seconds=int(get_env(dotenv, "RECEIVE_CODE_TIMEOUT_SECONDS", "60")),
        post_auth_timeout_seconds=int(get_env(dotenv, "POST_AUTH_TIMEOUT_SECONDS", "60")),
        poll_interval_seconds=float(get_env(dotenv, "POLL_INTERVAL_SECONDS", "1.0")),
    )


def import_stealth_server(stealth_repo_path: Path):
    server_path = stealth_repo_path / "src"
    if not server_path.exists():
        raise FileNotFoundError(
            f"Nao encontrei {server_path}. Rode ./install_stealth_browser.sh antes."
        )
    sys.path.insert(0, str(server_path))

    import server as stealth_server  # type: ignore

    return stealth_server


async def call_tool(stealth_server, tool_name: str, *args, **kwargs):
    """
    Call either a plain async function or a FastMCP FunctionTool (.fn).
    """
    tool = getattr(stealth_server, tool_name)
    fn = getattr(tool, "fn", tool)
    return await fn(*args, **kwargs)


async def get_page_content_safe(stealth_server, instance_id: str) -> Dict[str, str]:
    """
    Avoid server.get_page_content(), which may fail serialization in response_handler.
    """
    def _to_safe_string(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        try:
            return str(value)
        except Exception:
            return repr(value)

    tab = await stealth_server.browser_manager.get_tab(instance_id)
    if not tab:
        raise Exception(f"Instance not found: {instance_id}")

    # Some pages temporarily return non-serializable CDP objects (e.g. ExceptionDetails).
    # Retry briefly and always normalize fields to plain strings.
    for attempt in range(3):
        try:
            raw = await stealth_server.dom_handler.get_page_content(tab, include_frames=False)
            return {
                "html": _to_safe_string(raw.get("html")),
                "text": _to_safe_string(raw.get("text")),
                "url": _to_safe_string(raw.get("url")),
                "title": _to_safe_string(raw.get("title")),
            }
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(0.3)

    return {"html": "", "text": "", "url": "", "title": ""}


async def wait_for_text(stealth_server, instance_id: str, expected_text: str, timeout_seconds: int, poll_interval: float) -> Dict[str, str]:
    start = time.monotonic()
    while True:
        content = await get_page_content_safe(stealth_server, instance_id)
        page_text = (content.get("text") or "")
        if expected_text in page_text:
            return content

        if time.monotonic() - start >= timeout_seconds:
            raise TimeoutError(f"Timeout aguardando texto '{expected_text}'. URL atual: {content.get('url')}")

        await asyncio.sleep(poll_interval)


async def wait_for_redirect(stealth_server, instance_id: str, initial_url: str, expected_text: str, timeout_seconds: int, poll_interval: float) -> Dict[str, str]:
    start = time.monotonic()
    last_url = initial_url

    while True:
        content = await get_page_content_safe(stealth_server, instance_id)
        current_url = content.get("url") or ""
        text = content.get("text") or ""

        if current_url != last_url:
            log("REDIRECT", f"URL mudou: {last_url} -> {current_url}")
            last_url = current_url

        redirected = current_url != initial_url
        text_ok = (not expected_text) or (expected_text in text)

        if redirected and text_ok:
            return content

        if time.monotonic() - start >= timeout_seconds:
            raise TimeoutError(
                "Timeout aguardando redirect. "
                f"URL inicial: {initial_url} | URL atual: {current_url} | "
                f"Texto esperado no redirect: '{expected_text or '(nao definido)'}'"
            )

        await asyncio.sleep(poll_interval)


async def run_flow(config: Config) -> None:
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    stealth_server = import_stealth_server(config.stealth_path)

    log("INIT", f"Stealth Browser MCP: {config.stealth_path}")
    log("INIT", f"Modo: {'headless' if config.headless else 'headed'}")
    log("INIT", f"Sandbox: {config.sandbox}")

    instance = await call_tool(
        stealth_server,
        "spawn_browser",
        headless=config.headless,
        sandbox=config.sandbox,
    )
    instance_id = instance["instance_id"]
    log("BROWSER", f"Instancia criada: {instance_id}")

    try:
        log("STEP-1", f"Navegando para URL de login: {config.login_url}")
        nav = await call_tool(stealth_server, "navigate", instance_id=instance_id, url=config.login_url)
        initial_url = nav.get("url") or config.login_url
        log("STEP-1", f"URL apos primeira navegacao: {initial_url}")

        log("STEP-1", "Aguardando redirect e validacao de texto da pagina...")
        redirect_content = await wait_for_redirect(
            stealth_server=stealth_server,
            instance_id=instance_id,
            initial_url=initial_url,
            expected_text=config.redirect_validation_text,
            timeout_seconds=config.redirect_timeout_seconds,
            poll_interval=config.poll_interval_seconds,
        )
        redirected_url = redirect_content.get("url") or ""
        log("STEP-1", f"Redirect confirmado para: {redirected_url}")

        if config.redirect_validation_text:
            log("STEP-1", f"Texto de validacao encontrado no redirect: '{config.redirect_validation_text}'")

        log("STEP-2", "Preenchendo CPF")
        await call_tool(
            stealth_server,
            "type_text",
            instance_id=instance_id,
            selector=config.cpf_selector,
            text=config.cpf,
            clear_first=True,
        )

        log("STEP-2", "Preenchendo SENHA")
        await call_tool(
            stealth_server,
            "type_text",
            instance_id=instance_id,
            selector=config.senha_selector,
            text=config.senha,
            clear_first=True,
        )

        pre_click_shot = artifacts_dir / f"01_before_entrar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        log("STEP-2", f"Salvando screenshot antes do click: {pre_click_shot}")
        await call_tool(
            stealth_server,
            "take_screenshot",
            instance_id=instance_id,
            file_path=str(pre_click_shot.resolve()),
        )

        log("STEP-3", "Clicando no botao ENTRAR")
        await call_tool(
            stealth_server,
            "click_element",
            instance_id=instance_id,
            selector=config.entrar_selector,
            text_match=config.entrar_text,
        )

        post_click_shot = artifacts_dir / f"02_after_entrar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        log("STEP-3", f"Salvando screenshot apos click: {post_click_shot}")
        await call_tool(
            stealth_server,
            "take_screenshot",
            instance_id=instance_id,
            file_path=str(post_click_shot.resolve()),
        )

        if config.post_login_validation_text:
            log("STEP-3", f"Aguardando texto de validacao pos-login: '{config.post_login_validation_text}'")
            post_login_content = await wait_for_text(
                stealth_server=stealth_server,
                instance_id=instance_id,
                expected_text=config.post_login_validation_text,
                timeout_seconds=config.post_login_timeout_seconds,
                poll_interval=config.poll_interval_seconds,
            )
            log("STEP-3", f"Validacao pos-login OK. URL atual: {post_login_content.get('url')}")

        if config.receive_code_text:
            log("STEP-4", f"Clicando no botao: '{config.receive_code_text}'")
            await call_tool(
                stealth_server,
                "click_element",
                instance_id=instance_id,
                selector=config.receive_code_selector,
                text_match=config.receive_code_text,
            )

            step4_shot = artifacts_dir / f"03_after_receive_code_click_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            log("STEP-4", f"Salvando screenshot apos click em receber codigo: {step4_shot}")
            await call_tool(
                stealth_server,
                "take_screenshot",
                instance_id=instance_id,
                file_path=str(step4_shot.resolve()),
            )

            if config.receive_code_validation_text:
                log("STEP-4", f"Aguardando texto de validacao apos receber codigo: '{config.receive_code_validation_text}'")
                receive_code_content = await wait_for_text(
                    stealth_server=stealth_server,
                    instance_id=instance_id,
                    expected_text=config.receive_code_validation_text,
                    timeout_seconds=config.receive_code_timeout_seconds,
                    poll_interval=config.poll_interval_seconds,
                )
                log("STEP-4", f"Validacao apos receber codigo OK. URL atual: {receive_code_content.get('url')}")

                if config.headless:
                    otp_code = await asyncio.to_thread(input, "Digite o codigo recebido por e-mail: ")
                    otp_code = otp_code.strip()
                    if not otp_code:
                        raise ValueError("Codigo OTP vazio. Encerrando fluxo.")

                    log("STEP-5", "Preenchendo codigo recebido no campo OTP")
                    await call_tool(
                        stealth_server,
                        "type_text",
                        instance_id=instance_id,
                        selector=config.otp_input_selector,
                        text=otp_code,
                        clear_first=True,
                    )

                    log("STEP-5", f"Clicando no botao: '{config.authenticate_button_text}'")
                    await call_tool(
                        stealth_server,
                        "click_element",
                        instance_id=instance_id,
                        selector=config.authenticate_button_selector,
                        text_match=config.authenticate_button_text,
                    )

                    step5_shot = artifacts_dir / f"04_after_authenticate_click_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    log("STEP-5", f"Salvando screenshot apos click em autenticar: {step5_shot}")
                    await call_tool(
                        stealth_server,
                        "take_screenshot",
                        instance_id=instance_id,
                        file_path=str(step5_shot.resolve()),
                    )

                    if config.post_auth_validation_text:
                        log("STEP-5", f"Aguardando texto de validacao pos-autenticacao: '{config.post_auth_validation_text}'")
                        post_auth_content = await wait_for_text(
                            stealth_server=stealth_server,
                            instance_id=instance_id,
                            expected_text=config.post_auth_validation_text,
                            timeout_seconds=config.post_auth_timeout_seconds,
                            poll_interval=config.poll_interval_seconds,
                        )
                        log("STEP-5", f"Validacao pos-autenticacao OK. URL atual: {post_auth_content.get('url')}")

        log("DONE", "Fluxo concluido com sucesso.")
        log("DONE", f"URL atual apos login: {(await get_page_content_safe(stealth_server, instance_id)).get('url')}")
        log("DONE", f"Screenshots salvos em: {artifacts_dir.resolve()}")

        if config.keep_browser_open:
            log("HOLD", "Navegador sera mantido aberto. Use Ctrl+C para encerrar o script.")
            while True:
                await asyncio.sleep(3600)

    except KeyboardInterrupt:
        log("EXIT", "Interrompido pelo usuario.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fluxo de login com stealth-browser-mcp")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--headless", action="store_true", help="Forca modo headless")
    mode.add_argument("--headed", action="store_true", help="Forca modo headed")
    parser.add_argument("--no-keep-open", action="store_true", help="Nao manter o navegador aberto ao final")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = build_config(args)
    asyncio.run(run_flow(config))


if __name__ == "__main__":
    main()
