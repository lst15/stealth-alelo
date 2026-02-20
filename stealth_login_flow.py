#!/usr/bin/env python3
import argparse
import asyncio
import os
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from urllib.parse import urlparse

DEFAULT_ENV_FILES = [
    "env/runtime.env",
    "env/credentials.env",
    "env/selectors.env",
    "env/validation.env",
    "env/timeouts.env",
]


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


def resolve_env_files() -> list[Path]:
    raw = os.environ.get("ENV_FILES", ",".join(DEFAULT_ENV_FILES))
    return [Path(p.strip()) for p in raw.split(",") if p.strip()]


def load_environment() -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for env_file in resolve_env_files():
        merged.update(load_dotenv_file(env_file))
    return merged


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
    dashboard_url: str
    dashboard_path_fragment: str
    boletos_url: str
    boletos_page_validation_text: str
    boletos_produto_field_text: str
    boletos_status_field_text: str
    boletos_status_option_text: str
    boletos_buscar_button_text: str
    boletos_results_current_text: str
    boletos_results_target_text: str
    boletos_produto_trigger_selector: str
    boletos_status_trigger_selector: str
    boletos_buscar_selector: str
    boletos_results_trigger_selector: str
    boletos_results_option_selector: str
    boletos_filter_scope_selector: str
    boletos_download_link_text: str
    boletos_download_scope_selector: str
    boletos_pagination_scope_selector: str
    user_data_dir: str
    background_headed: bool
    resume_session: bool
    sandbox: bool
    keep_browser_open: bool
    redirect_timeout_seconds: int
    post_login_timeout_seconds: int
    receive_code_timeout_seconds: int
    post_auth_timeout_seconds: int
    dashboard_timeout_seconds: int
    boletos_timeout_seconds: int
    boletos_download_timeout_seconds: int
    boletos_pagination_timeout_seconds: int
    boletos_pagination_max_pages: int
    poll_interval_seconds: float


def build_config(args: argparse.Namespace) -> Config:
    dotenv = load_environment()

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
        loaded_files = ", ".join(str(p) for p in resolve_env_files())
        raise ValueError(
            f"Variaveis obrigatorias ausentes ({', '.join(missing)}). "
            f"Arquivos avaliados: {loaded_files}"
        )

    background_headed = parse_bool(get_env(dotenv, "BACKGROUND_HEADED"), default=False)
    resume_session = parse_bool(get_env(dotenv, "RESUME_SESSION"), default=False)
    if args.background_headed:
        background_headed = True
    elif args.headed:
        background_headed = False
    if args.resume_session:
        resume_session = True

    keep_open = parse_bool(get_env(dotenv, "KEEP_BROWSER_OPEN"), default=True)
    if args.no_keep_open:
        keep_open = False

    stealth_path = Path(get_env(dotenv, "STEALTH_BROWSER_MCP_PATH", ".stealth-browser-mcp")).resolve()

    post_auth_validation_text = (
        get_env(dotenv, "STEP5_VALIDATION_TEXT")
        or get_env(dotenv, "POST_AUTH_VALIDATION_TEXT", "")
    ).strip()

    if resume_session and not post_auth_validation_text:
        raise ValueError(
            "Para --resume-session, defina STEP5_VALIDATION_TEXT em env/validation.env "
            "(ex.: STEP5_VALIDATION_TEXT=Acompanhe)."
        )

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
        post_auth_validation_text=post_auth_validation_text,
        dashboard_url=get_env(dotenv, "DASHBOARD_URL", "https://prepagos.alelo.com.br/dashboard"),
        dashboard_path_fragment=get_env(dotenv, "DASHBOARD_PATH_FRAGMENT", urlparse(get_env(dotenv, "DASHBOARD_URL", "https://prepagos.alelo.com.br/dashboard")).path or "/dashboard"),
        boletos_url=get_env(dotenv, "BOLETOS_URL", "https://prepagos.alelo.com.br/financeiro/boletos"),
        boletos_page_validation_text=get_env(dotenv, "BOLETOS_PAGE_VALIDATION_TEXT", "Consulte seus boletos emitidos"),
        boletos_produto_field_text=get_env(dotenv, "BOLETOS_PRODUTO_FIELD_TEXT", "Produto"),
        boletos_status_field_text=get_env(dotenv, "BOLETOS_STATUS_FIELD_TEXT", "Status"),
        boletos_status_option_text=get_env(dotenv, "BOLETOS_STATUS_OPTION_TEXT", "Pagamento Pendente"),
        boletos_buscar_button_text=get_env(dotenv, "BOLETOS_BUSCAR_BUTTON_TEXT", "BUSCAR"),
        boletos_results_current_text=get_env(dotenv, "BOLETOS_RESULTS_CURRENT_TEXT", "5 Resultados"),
        boletos_results_target_text=get_env(dotenv, "BOLETOS_RESULTS_TARGET_TEXT", "50 Resultados"),
        boletos_produto_trigger_selector=get_env(
            dotenv,
            "BOLETOS_PRODUTO_TRIGGER_SELECTOR",
            'ng-select[placeholder*="Produto" i], [aria-label*="Produto" i], .ng-select',
        ),
        boletos_status_trigger_selector=get_env(
            dotenv,
            "BOLETOS_STATUS_TRIGGER_SELECTOR",
            'ng-select[placeholder*="Status" i], [aria-label*="Status" i], .ng-select',
        ),
        boletos_buscar_selector=get_env(
            dotenv,
            "BOLETOS_BUSCAR_SELECTOR",
            'button, [role="button"], a',
        ),
        boletos_results_trigger_selector=get_env(
            dotenv,
            "BOLETOS_RESULTS_TRIGGER_SELECTOR",
            '[role="combobox"], .ng-select, .p-dropdown, .mat-select',
        ),
        boletos_results_option_selector=get_env(
            dotenv,
            "BOLETOS_RESULTS_OPTION_SELECTOR",
            '.ng-dropdown-panel .ng-option, [role="listbox"] [role="option"], .p-dropdown-panel .p-dropdown-item, .mat-select-panel .mat-option, li',
        ),
        boletos_filter_scope_selector=get_env(
            dotenv,
            "BOLETOS_FILTER_SCOPE_SELECTOR",
            ".controls.line1",
        ),
        boletos_download_link_text=get_env(dotenv, "BOLETOS_DOWNLOAD_LINK_TEXT", "BAIXAR BOLETO"),
        boletos_download_scope_selector=get_env(
            dotenv,
            "BOLETOS_DOWNLOAD_SCOPE_SELECTOR",
            ".table-responsive, table, .datatable, .ui-table, .card-body",
        ),
        boletos_pagination_scope_selector=get_env(
            dotenv,
            "BOLETOS_PAGINATION_SCOPE_SELECTOR",
            ".table-responsive, .datatable, .ui-table, .card-body",
        ),
        user_data_dir=get_env(dotenv, "USER_DATA_DIR", str(Path(".browser-profile").resolve())),
        background_headed=background_headed,
        resume_session=resume_session,
        sandbox=parse_bool(get_env(dotenv, "BROWSER_SANDBOX"), default=False),
        keep_browser_open=keep_open,
        redirect_timeout_seconds=int(get_env(dotenv, "REDIRECT_TIMEOUT_SECONDS", "60")),
        post_login_timeout_seconds=int(get_env(dotenv, "POST_LOGIN_TIMEOUT_SECONDS", "60")),
        receive_code_timeout_seconds=int(get_env(dotenv, "RECEIVE_CODE_TIMEOUT_SECONDS", "60")),
        post_auth_timeout_seconds=int(get_env(dotenv, "POST_AUTH_TIMEOUT_SECONDS", "60")),
        dashboard_timeout_seconds=int(get_env(dotenv, "DASHBOARD_TIMEOUT_SECONDS", "60")),
        boletos_timeout_seconds=int(get_env(dotenv, "BOLETOS_TIMEOUT_SECONDS", "60")),
        boletos_download_timeout_seconds=int(get_env(dotenv, "BOLETOS_DOWNLOAD_TIMEOUT_SECONDS", "45")),
        boletos_pagination_timeout_seconds=int(get_env(dotenv, "BOLETOS_PAGINATION_TIMEOUT_SECONDS", "30")),
        boletos_pagination_max_pages=int(get_env(dotenv, "BOLETOS_PAGINATION_MAX_PAGES", "200")),
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
            raise TimeoutError(f"Timeout aguardando texto '{expected_text}'.")

        await asyncio.sleep(poll_interval)


async def wait_for_redirect(stealth_server, instance_id: str, initial_url: str, expected_text: str, timeout_seconds: int, poll_interval: float) -> Dict[str, str]:
    start = time.monotonic()
    last_url = initial_url

    while True:
        content = await get_page_content_safe(stealth_server, instance_id)
        current_url = content.get("url") or ""
        text = content.get("text") or ""

        if current_url != last_url:
            log("REDIRECT", "Mudanca de URL detectada durante redirect")
            last_url = current_url

        redirected = current_url != initial_url
        text_ok = (not expected_text) or (expected_text in text)

        if redirected and text_ok:
            return content

        if time.monotonic() - start >= timeout_seconds:
            raise TimeoutError(
                "Timeout aguardando redirect. "
                f"Texto esperado no redirect: '{expected_text or '(nao definido)'}'"
            )

        await asyncio.sleep(poll_interval)


async def wait_for_url_contains(
    stealth_server,
    instance_id: str,
    fragment: str,
    timeout_seconds: int,
    poll_interval: float,
) -> Dict[str, str]:
    start = time.monotonic()
    frag = (fragment or "").lower()
    while True:
        content = await get_page_content_safe(stealth_server, instance_id)
        url = (content.get("url") or "").lower()
        if frag in url:
            return content
        if time.monotonic() - start >= timeout_seconds:
            raise TimeoutError(f"Timeout aguardando rota contendo '{fragment}'.")
        await asyncio.sleep(poll_interval)


def build_screenshot_path(artifacts_dir: Path, prefix: str) -> Path:
    return artifacts_dir / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"


async def save_screenshot(stealth_server, instance_id: str, file_path: Path, step: str, message: str) -> None:
    log(step, f"{message}: {file_path}")
    await call_tool(
        stealth_server,
        "take_screenshot",
        instance_id=instance_id,
        file_path=str(file_path.resolve()),
    )


async def validate_text_if_configured(
    stealth_server,
    instance_id: str,
    expected_text: str,
    timeout_seconds: int,
    poll_interval: float,
    step: str,
    wait_message: str,
    ok_message: str,
) -> None:
    if not expected_text:
        return
    log(step, f"{wait_message}: '{expected_text}'")
    await wait_for_text(
        stealth_server=stealth_server,
        instance_id=instance_id,
        expected_text=expected_text,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
    )
    log(step, ok_message)


async def click_text_anywhere(stealth_server, instance_id: str, text_value: str) -> bool:
    script = r"""
        const norm = (v) => (v || '')
          .normalize('NFD')
          .replace(/[\u0300-\u036f]/g, '')
          .replace(/\s+/g, ' ')
          .toLowerCase()
          .trim();
        const target = norm(arguments[0] || '');
        const selectors = 'button,a,input,div,span,li,[role="button"],[role="option"],.ng-option,.mat-option,.p-dropdown-item';
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const textOf = (el) => norm((el.innerText || el.textContent || el.value || '') + '');
        for (const el of document.querySelectorAll(selectors)) {
            const txt = textOf(el);
            if (!txt || !isVisible(el)) continue;
            if (txt.includes(target)) {
                el.click();
                return true;
            }
        }
        return false;
    """
    result = await call_tool(
        stealth_server,
        "execute_script",
        instance_id=instance_id,
        script=script,
        args=[text_value],
    )
    if isinstance(result, dict) and result.get("success") and result.get("result") is True:
        return True

    try:
        return await call_tool(
            stealth_server,
            "click_element",
            instance_id=instance_id,
            selector='button, a, input, div, span, li, [role="button"], [role="option"]',
            text_match=text_value,
        )
    except Exception:
        return False


async def debug_collect_visible_texts(stealth_server, instance_id: str, selectors: str, limit: int = 20) -> list[str]:
    script = r"""
        const selectors = arguments[0] || '*';
        const limit = Number(arguments[1] || 20);
        const norm = (v) => (v || '').replace(/\s+/g, ' ').trim();
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const out = [];
        for (const el of document.querySelectorAll(selectors)) {
            if (!isVisible(el)) continue;
            const txt = norm(el.innerText || el.textContent || el.value || '');
            if (!txt) continue;
            out.push(txt);
            if (out.length >= limit) break;
        }
        return out;
    """
    try:
        result = await call_tool(
            stealth_server,
            "execute_script",
            instance_id=instance_id,
            script=script,
            args=[selectors, limit],
        )
        if isinstance(result, dict) and result.get("success") and isinstance(result.get("result"), list):
            return [str(v) for v in result.get("result")]
    except Exception:
        pass
    return []


async def wait_for_open_options_panel(
    stealth_server,
    instance_id: str,
    timeout_seconds: float = 6.0,
    poll_interval: float = 0.2,
) -> bool:
    start = time.monotonic()
    script = r"""
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const panels = [...document.querySelectorAll('.ng-dropdown-panel,.p-dropdown-panel,.mat-select-panel,[role="listbox"],.cdk-overlay-pane')]
          .filter(isVisible);
        for (const p of panels) {
            const opts = p.querySelectorAll('.ng-option,.p-dropdown-item,.mat-option,[role="option"],li');
            if (opts.length > 0) return true;
        }
        return false;
    """
    while True:
        try:
            result = await call_tool(
                stealth_server,
                "execute_script",
                instance_id=instance_id,
                script=script,
            )
            if isinstance(result, dict) and result.get("success") and result.get("result") is True:
                return True
        except Exception:
            pass
        if time.monotonic() - start >= timeout_seconds:
            return False
        await asyncio.sleep(poll_interval)


async def open_status_dropdown_strict(stealth_server, instance_id: str, scope_selector: str) -> bool:
    script = r"""
        const scopeSelector = arguments[0] || '.controls.line1';
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const scope = document.querySelector(scopeSelector);
        if (!scope || !isVisible(scope)) return false;
        const selects = [...scope.querySelectorAll('ng-select,.ng-select,[role="combobox"],.p-dropdown,.mat-select')].filter(isVisible);
        if (selects.length < 2) return false;
        const status = selects[1];
        const trigger = status.querySelector('.ng-select-container,.ng-arrow-wrapper,.p-dropdown-trigger,.mat-select-trigger,span,input') || status;
        status.click();
        trigger.click();
        status.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
        status.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
        status.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        return true;
    """
    try:
        result = await call_tool(
            stealth_server,
            "execute_script",
            instance_id=instance_id,
            script=script,
            args=[scope_selector],
        )
        return bool(isinstance(result, dict) and result.get("success") and result.get("result") is True)
    except Exception:
        return False


async def select_option_from_open_dropdown(stealth_server, instance_id: str, option_text: str) -> bool:
    script = r"""
        const norm = (v) => (v || '')
          .normalize('NFD')
          .replace(/[\u0300-\u036f]/g, '')
          .replace(/\s+/g, ' ')
          .toLowerCase()
          .trim();
        const target = norm(arguments[0] || '');
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const panels = [...document.querySelectorAll('.ng-dropdown-panel,.p-dropdown-panel,.mat-select-panel,[role=\"listbox\"],.cdk-overlay-pane')].filter(isVisible);
        for (const panel of panels) {
            const options = panel.querySelectorAll('.ng-option,.p-dropdown-item,.mat-option,[role=\"option\"],li');
            for (const el of options) {
                if (!isVisible(el)) continue;
                const txt = norm(el.innerText || el.textContent || '');
                if (!txt) continue;
                if (txt.includes(target)) {
                    el.click();
                    return true;
                }
            }
        }
        return false;
    """
    try:
        result = await call_tool(
            stealth_server,
            "execute_script",
            instance_id=instance_id,
            script=script,
            args=[option_text],
        )
        return bool(isinstance(result, dict) and result.get("success") and result.get("result") is True)
    except Exception:
        return False


async def open_produto_dropdown_strict(stealth_server, instance_id: str, scope_selector: str) -> bool:
    script = r"""
        const scopeSelector = arguments[0] || '.controls.line1';
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const scope = document.querySelector(scopeSelector);
        if (!scope || !isVisible(scope)) return false;
        const selects = [...scope.querySelectorAll('ng-select,.ng-select,[role="combobox"],.p-dropdown,.mat-select')].filter(isVisible);
        if (selects.length < 1) return false;
        const produto = selects[0];
        const trigger = produto.querySelector('.ng-select-container,.ng-arrow-wrapper,.p-dropdown-trigger,.mat-select-trigger,span,input') || produto;
        produto.click();
        trigger.click();
        produto.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
        produto.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
        produto.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        return true;
    """
    try:
        result = await call_tool(
            stealth_server,
            "execute_script",
            instance_id=instance_id,
            script=script,
            args=[scope_selector],
        )
        return bool(isinstance(result, dict) and result.get("success") and result.get("result") is True)
    except Exception:
        return False


async def get_filter_dropdown_value_text(
    stealth_server,
    instance_id: str,
    scope_selector: str,
    dropdown_index: int,
) -> str:
    script = r"""
        const scopeSelector = arguments[0] || '.controls.line1';
        const idx = Number(arguments[1] || 0);
        const norm = (v) => (v || '').replace(/\s+/g, ' ').trim();
        const scope = document.querySelector(scopeSelector);
        if (!scope) return '';
        const selects = [...scope.querySelectorAll('ng-select,.ng-select,[role="combobox"],.p-dropdown,.mat-select')];
        if (!selects[idx]) return '';
        const host = selects[idx];
        const valueEl = host.querySelector(
          '.ng-value-label,.ng-value,.p-dropdown-label,.mat-select-value-text,.mat-select-value,.ng-input input,[aria-activedescendant],span,input'
        );
        return norm((valueEl && (valueEl.innerText || valueEl.textContent || valueEl.value)) || host.innerText || '');
    """
    try:
        result = await call_tool(
            stealth_server,
            "execute_script",
            instance_id=instance_id,
            script=script,
            args=[scope_selector, dropdown_index],
        )
        if isinstance(result, dict) and result.get("success"):
            return str(result.get("result") or "").strip()
    except Exception:
        pass
    return ""


async def produto_selected_ok(stealth_server, instance_id: str, scope_selector: str) -> bool:
    script = r"""
        const scopeSelector = arguments[0] || '.controls.line1';
        const norm = (v) => (v || '')
          .normalize('NFD')
          .replace(/[\u0300-\u036f]/g, '')
          .replace(/\s+/g, ' ')
          .toLowerCase()
          .trim();
        const scope = document.querySelector(scopeSelector);
        if (!scope) return false;
        const selects = [...scope.querySelectorAll('ng-select,.ng-select,[role="combobox"],.p-dropdown,.mat-select')];
        if (selects[0]) {
            const produto = selects[0];
            if (produto.classList.contains('ng-has-value')) return true;
            const txtProduto = norm(produto.innerText || produto.textContent || '');
            if (txtProduto && txtProduto !== 'produto') {
                if (txtProduto.includes('selected') || txtProduto.includes('contrato') || txtProduto.includes('incentivo')) {
                    return true;
                }
            }
        }
        // Fallback: check full filter scope text for accessibility pattern indicating selected option.
        const txtScope = norm(scope.innerText || scope.textContent || '');
        if (!txtScope) return false;
        if (txtScope.includes('option') && txtScope.includes('selected') && (txtScope.includes('contrato') || txtScope.includes('incentivo'))) {
            return true;
        }
        return false;
    """
    try:
        result = await call_tool(
            stealth_server,
            "execute_script",
            instance_id=instance_id,
            script=script,
            args=[scope_selector],
        )
        return bool(isinstance(result, dict) and result.get("success") and result.get("result") is True)
    except Exception:
        return False


async def select_status_option_in_scope(
    stealth_server,
    instance_id: str,
    scope_selector: str,
    option_text: str,
) -> bool:
    script = r"""
        const scopeSelector = arguments[0] || '.controls.line1';
        const targetRaw = arguments[1] || '';
        const norm = (v) => (v || '')
          .normalize('NFD')
          .replace(/[\u0300-\u036f]/g, '')
          .replace(/\s+/g, ' ')
          .toLowerCase()
          .trim();
        const target = norm(targetRaw);
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const textOf = (el) => norm(el.innerText || el.textContent || '');
        const scope = document.querySelector(scopeSelector);
        if (!scope || !isVisible(scope)) return false;

        const candidates = [...scope.querySelectorAll('.ng-option,[role="option"],li,span,div')]
          .filter(isVisible)
          .map((el) => ({ el, txt: textOf(el) }))
          .filter((x) => !!x.txt);

        // Prefer exact match first.
        for (const c of candidates) {
            if (c.txt === target) {
                c.el.click();
                return true;
            }
        }
        // Then fallback to contains.
        for (const c of candidates) {
            if (c.txt.includes(target)) {
                c.el.click();
                return true;
            }
        }
        return false;
    """
    try:
        result = await call_tool(
            stealth_server,
            "execute_script",
            instance_id=instance_id,
            script=script,
            args=[scope_selector, option_text],
        )
        return bool(isinstance(result, dict) and result.get("success") and result.get("result") is True)
    except Exception:
        return False


async def select_first_option_in_scope(stealth_server, instance_id: str, scope_selector: str) -> bool:
    script = r"""
        const scopeSelector = arguments[0] || '.controls.line1';
        const norm = (v) => (v || '')
          .normalize('NFD')
          .replace(/[\u0300-\u036f]/g, '')
          .replace(/\s+/g, ' ')
          .toLowerCase()
          .trim();
        const skip = ['produto', 'status', 'buscar', 'filtrar registros', 'nº do pedido', 'de', 'ate'];
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const scope = document.querySelector(scopeSelector);
        if (!scope || !isVisible(scope)) return false;

        const options = [...scope.querySelectorAll('.ng-option,[role="option"],li,span,div')]
          .filter(isVisible)
          .map((el) => ({ el, txt: norm(el.innerText || el.textContent || '') }))
          .filter((x) => x.txt && !skip.some((s) => x.txt === s || x.txt.includes(s + ' ')));

        for (const item of options) {
            if (item.txt.length < 2) continue;
            item.el.click();
            return true;
        }
        return false;
    """
    try:
        result = await call_tool(
            stealth_server,
            "execute_script",
            instance_id=instance_id,
            script=script,
            args=[scope_selector],
        )
        return bool(isinstance(result, dict) and result.get("success") and result.get("result") is True)
    except Exception:
        return False


async def click_first_open_dropdown_option(stealth_server, instance_id: str) -> bool:
    script = r"""
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const panels = [...document.querySelectorAll(
            '.ng-dropdown-panel, .p-dropdown-panel, .mat-select-panel, [role="listbox"], .cdk-overlay-pane'
        )].filter(isVisible);

        for (const panel of panels) {
            const candidates = panel.querySelectorAll(
                '.ng-option:not(.ng-option-disabled), .p-dropdown-item:not(.p-disabled), .mat-option:not(.mat-option-disabled), [role="option"], li:not(.disabled)'
            );
            for (const el of candidates) {
                const txt = ((el.innerText || el.textContent || '') + '').trim();
                if (!txt || !isVisible(el)) continue;
                el.click();
                return true;
            }
        }
        return false;
    """
    result = await call_tool(
        stealth_server,
        "execute_script",
        instance_id=instance_id,
        script=script,
    )
    return bool(isinstance(result, dict) and result.get("success") and result.get("result") is True)


async def press_key_on_active_element(stealth_server, instance_id: str, key: str) -> bool:
    script = r"""
        const key = arguments[0];
        const target = document.activeElement || document.body;
        if (!target) return false;
        const down = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
        const up = new KeyboardEvent('keyup', { key, bubbles: true, cancelable: true });
        target.dispatchEvent(down);
        target.dispatchEvent(up);
        return true;
    """
    result = await call_tool(
        stealth_server,
        "execute_script",
        instance_id=instance_id,
        script=script,
        args=[key],
    )
    return bool(isinstance(result, dict) and result.get("success") and result.get("result") is True)


async def click_by_selector_then_text_fallback(
    stealth_server,
    instance_id: str,
    selector: str,
    text_value: str,
) -> bool:
    script = r"""
        const selector = arguments[0] || '';
        const target = (arguments[1] || '').toLowerCase().trim();
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const textOf = (el) => ((
            el.innerText ||
            el.textContent ||
            el.getAttribute('placeholder') ||
            el.getAttribute('aria-label') ||
            ''
        ) + '').toLowerCase().trim();

        const candidates = [...document.querySelectorAll(selector)].filter(isVisible);
        if (candidates.length === 0) return false;

        for (const el of candidates) {
            const txt = textOf(el);
            if (target && txt.includes(target)) {
                el.click();
                return true;
            }
        }
        candidates[0].click();
        return true;
    """
    try:
        result = await call_tool(
            stealth_server,
            "execute_script",
            instance_id=instance_id,
            script=script,
            args=[selector, text_value],
        )
        if isinstance(result, dict) and result.get("success") and result.get("result") is True:
            return True
    except Exception:
        pass

    return await click_text_anywhere(stealth_server, instance_id, text_value)


def snapshot_download_dir(download_dir: Path) -> Dict[str, tuple[int, int]]:
    state: Dict[str, tuple[int, int]] = {}
    for entry in download_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.name.endswith((".crdownload", ".part", ".tmp")):
            continue
        try:
            stat = entry.stat()
            state[entry.name] = (stat.st_size, stat.st_mtime_ns)
        except FileNotFoundError:
            continue
    return state


def detect_new_download_file(download_dir: Path, before: Dict[str, tuple[int, int]]) -> Optional[Path]:
    current = snapshot_download_dir(download_dir)
    for name, info in current.items():
        if name not in before:
            return download_dir / name
        if before[name] != info:
            return download_dir / name
    return None


def has_temp_download_files(download_dir: Path) -> bool:
    for entry in download_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.name.endswith((".crdownload", ".part", ".tmp")):
            return True
    return False


def rename_download_with_timestamp(downloaded_file: Path, sequence: int) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = downloaded_file.suffix
    stem = downloaded_file.stem
    target = downloaded_file.with_name(f"{stem}_{ts}_{sequence:03d}{suffix}")
    attempt = 1
    while target.exists():
        target = downloaded_file.with_name(f"{stem}_{ts}_{sequence:03d}_{attempt}{suffix}")
        attempt += 1
    downloaded_file.rename(target)
    return target


async def wait_for_download_file(
    download_dir: Path,
    before: Dict[str, tuple[int, int]],
    timeout_seconds: float,
    poll_interval: float,
) -> Optional[Path]:
    start = time.monotonic()
    stable_no_temp_cycles = 0
    while True:
        found = detect_new_download_file(download_dir, before)
        if found is not None:
            if has_temp_download_files(download_dir):
                stable_no_temp_cycles = 0
            else:
                stable_no_temp_cycles += 1
                # Require a few consecutive checks without temp files to avoid
                # racing with late .crdownload creation.
                if stable_no_temp_cycles >= 3:
                    return found
        if time.monotonic() - start >= timeout_seconds:
            if found is not None and not has_temp_download_files(download_dir):
                return found
            return None
        await asyncio.sleep(poll_interval)


async def configure_browser_download_dir(stealth_server, instance_id: str, download_dir: Path) -> None:
    tab = await stealth_server.browser_manager.get_tab(instance_id)
    if not tab:
        raise RuntimeError(f"Instancia nao encontrada para download: {instance_id}")
    await tab.set_download_path(str(download_dir.resolve()))


async def count_visible_text_clickables(
    stealth_server,
    instance_id: str,
    scope_selector: str,
    text_value: str,
) -> int:
    script = r"""
        const scopeSelector = arguments[0] || '';
        const targetRaw = arguments[1] || '';
        const norm = (v) => (v || '')
          .normalize('NFD')
          .replace(/[\u0300-\u036f]/g, '')
          .replace(/\s+/g, ' ')
          .toLowerCase()
          .trim();
        const target = norm(targetRaw);
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const textOf = (el) => norm(el.innerText || el.textContent || el.value || '');
        const roots = scopeSelector ? [...document.querySelectorAll(scopeSelector)] : [document];
        const out = [];
        const seen = new Set();
        const clickablesSelector = 'a,button,[role="button"]';
        for (const root of roots) {
            for (const el of root.querySelectorAll(clickablesSelector)) {
                if (!isVisible(el)) continue;
                const txt = textOf(el);
                if (!txt || !txt.includes(target)) continue;
                const key = `${el.tagName}|${el.getAttribute('href') || ''}|${txt}`;
                if (seen.has(key)) continue;
                seen.add(key);
                out.push(el);
            }
        }
        return out.length;
    """
    try:
        result = await call_tool(
            stealth_server,
            "execute_script",
            instance_id=instance_id,
            script=script,
            args=[scope_selector, text_value],
        )
        if isinstance(result, dict) and result.get("success"):
            return int(result.get("result") or 0)
    except Exception:
        pass
    return 0


async def click_visible_text_clickable_by_index(
    stealth_server,
    instance_id: str,
    scope_selector: str,
    text_value: str,
    index: int,
) -> bool:
    script = r"""
        const scopeSelector = arguments[0] || '';
        const targetRaw = arguments[1] || '';
        const index = Number(arguments[2] || 0);
        const norm = (v) => (v || '')
          .normalize('NFD')
          .replace(/[\u0300-\u036f]/g, '')
          .replace(/\s+/g, ' ')
          .toLowerCase()
          .trim();
        const target = norm(targetRaw);
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const textOf = (el) => norm(el.innerText || el.textContent || el.value || '');
        const roots = scopeSelector ? [...document.querySelectorAll(scopeSelector)] : [document];
        const candidates = [];
        const seen = new Set();
        const clickablesSelector = 'a,button,[role="button"]';
        for (const root of roots) {
            for (const el of root.querySelectorAll(clickablesSelector)) {
                if (!isVisible(el)) continue;
                const txt = textOf(el);
                if (!txt || !txt.includes(target)) continue;
                const key = `${el.tagName}|${el.getAttribute('href') || ''}|${txt}`;
                if (seen.has(key)) continue;
                seen.add(key);
                candidates.push(el);
            }
        }
        if (index < 0 || index >= candidates.length) return false;
        const el = candidates[index];
        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
        el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
        el.click();
        return true;
    """
    try:
        result = await call_tool(
            stealth_server,
            "execute_script",
            instance_id=instance_id,
            script=script,
            args=[scope_selector, text_value, index],
        )
        return bool(isinstance(result, dict) and result.get("success") and result.get("result") is True)
    except Exception:
        return False


async def get_current_active_page_number(
    stealth_server,
    instance_id: str,
    scope_selector: str,
) -> Optional[int]:
    script = r"""
        const scopeSelector = arguments[0] || '';
        const roots = scopeSelector ? [...document.querySelectorAll(scopeSelector)] : [document];
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const numberFromText = (v) => {
            const t = (v || '').trim();
            if (!/^\d+$/.test(t)) return null;
            return Number(t);
        };
        const activeLike = (el) => {
            if (el.getAttribute('aria-current') === 'page') return true;
            const cls = ((el.className || '') + ' ' + ((el.parentElement && el.parentElement.className) || '')).toLowerCase();
            return cls.includes('active') || cls.includes('current') || cls.includes('selected');
        };
        for (const root of roots) {
            const candidates = root.querySelectorAll(
                '[aria-current=\"page\"], .active, .current, .selected, .page-item.active, .p-highlight, .mat-mdc-paginator-range-label, a, button, li, span, div'
            );
            for (const el of candidates) {
                if (!isVisible(el) || !activeLike(el)) continue;
                const n = numberFromText(el.innerText || el.textContent || '');
                if (Number.isInteger(n) && n > 0) return n;
            }
        }
        return null;
    """
    try:
        result = await call_tool(
            stealth_server,
            "execute_script",
            instance_id=instance_id,
            script=script,
            args=[scope_selector],
        )
        if isinstance(result, dict) and result.get("success"):
            value = result.get("result")
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
    except Exception:
        pass
    return None


async def click_pagination_page_number(
    stealth_server,
    instance_id: str,
    scope_selector: str,
    page_number: int,
) -> bool:
    script = r"""
        const scopeSelector = arguments[0] || '';
        const target = Number(arguments[1] || 0);
        if (!target || target < 1) return false;
        const roots = scopeSelector ? [...document.querySelectorAll(scopeSelector)] : [document];
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const numberFromText = (v) => {
            const t = (v || '').trim();
            if (!/^\d+$/.test(t)) return null;
            return Number(t);
        };
        const score = (el) => {
            const rect = el.getBoundingClientRect();
            const clsSelf = (el.className || '').toLowerCase();
            const clsParent = ((el.parentElement && el.parentElement.className) || '').toLowerCase();
            const aria = ((el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('role') || '')).toLowerCase();
            let s = 0;
            if (el.tagName === 'A' || el.tagName === 'BUTTON' || el.getAttribute('role') === 'button') s += 5;
            if ((clsSelf + ' ' + clsParent).includes('page') || (clsSelf + ' ' + clsParent).includes('paginator') || (clsSelf + ' ' + clsParent).includes('pagination')) s += 6;
            if (aria.includes('page') || aria.includes('pagin')) s += 3;
            if (rect.top > window.innerHeight * 0.45) s += 3;
            return s;
        };

        const candidates = [];
        for (const root of roots) {
            for (const el of root.querySelectorAll('a,button,[role="button"],li,span,div')) {
                if (!isVisible(el)) continue;
                const n = numberFromText(el.innerText || el.textContent || '');
                if (n !== target) continue;
                candidates.push({ el, score: score(el) });
            }
        }
        if (!candidates.length) return false;
        candidates.sort((a, b) => b.score - a.score);
        const best = candidates[0].el;
        best.scrollIntoView({ behavior: 'instant', block: 'center' });
        best.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
        best.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
        best.click();
        return true;
    """
    try:
        result = await call_tool(
            stealth_server,
            "execute_script",
            instance_id=instance_id,
            script=script,
            args=[scope_selector, page_number],
        )
        return bool(isinstance(result, dict) and result.get("success") and result.get("result") is True)
    except Exception:
        return False


async def wait_for_active_page(
    stealth_server,
    instance_id: str,
    scope_selector: str,
    target_page: int,
    timeout_seconds: float,
    poll_interval: float,
) -> bool:
    start = time.monotonic()
    while True:
        active = await get_current_active_page_number(stealth_server, instance_id, scope_selector)
        if active == target_page:
            return True
        if time.monotonic() - start >= timeout_seconds:
            return False
        await asyncio.sleep(poll_interval)


async def run_baixar_boletos_flow(stealth_server, config: Config, instance_id: str, artifacts_dir: Path, download_dir: Path) -> None:
    download_dir.mkdir(parents=True, exist_ok=True)
    log("BOLETOS", f"Diretorio de download selecionado: {download_dir}")
    await configure_browser_download_dir(stealth_server, instance_id, download_dir)
    log("BOLETOS", f"Diretorio de download configurado no browser: {download_dir}")

    log("BOLETOS", "Navegando para tela de boletos")
    await call_tool(
        stealth_server,
        "navigate",
        instance_id=instance_id,
        url=config.boletos_url,
    )
    await validate_text_if_configured(
        stealth_server=stealth_server,
        instance_id=instance_id,
        expected_text=config.boletos_page_validation_text,
        timeout_seconds=config.boletos_timeout_seconds,
        poll_interval=config.poll_interval_seconds,
        step="BOLETOS",
        wait_message="Aguardando validacao da pagina de boletos",
        ok_message="Validacao da pagina de boletos OK",
    )
    await save_screenshot(
        stealth_server,
        instance_id,
        build_screenshot_path(artifacts_dir, "05_boletos_page"),
        "BOLETOS",
        "Screenshot da pagina de boletos",
    )

    log("BOLETOS", "Selecionando primeira opcao do filtro Produto")
    opened_produto = await open_produto_dropdown_strict(
        stealth_server,
        instance_id,
        config.boletos_filter_scope_selector,
    )
    if not opened_produto:
        opened_produto = await click_by_selector_then_text_fallback(
            stealth_server,
            instance_id,
            config.boletos_produto_trigger_selector,
            config.boletos_produto_field_text,
        )
    if not opened_produto:
        raise RuntimeError("Nao foi possivel abrir o filtro Produto.")

    produto_clicked = False
    panel_open_produto = await wait_for_open_options_panel(stealth_server, instance_id, timeout_seconds=4.0, poll_interval=0.2)
    if panel_open_produto:
        produto_clicked = await click_first_open_dropdown_option(stealth_server, instance_id)
    if not produto_clicked:
        produto_clicked = await select_first_option_in_scope(
            stealth_server,
            instance_id,
            config.boletos_filter_scope_selector,
        )

    # Force commit in accessibility/select components.
    await press_key_on_active_element(stealth_server, instance_id, "Enter")
    await asyncio.sleep(0.12)
    await press_key_on_active_element(stealth_server, instance_id, "Tab")
    await asyncio.sleep(0.2)

    # Confirm selection was actually applied in the control.
    if not await produto_selected_ok(stealth_server, instance_id, config.boletos_filter_scope_selector):
        # ng-select fallback: keyboard confirm on active control
        await press_key_on_active_element(stealth_server, instance_id, "ArrowDown")
        await asyncio.sleep(0.15)
        await press_key_on_active_element(stealth_server, instance_id, "Enter")
        await asyncio.sleep(0.12)
        await press_key_on_active_element(stealth_server, instance_id, "Tab")
        await asyncio.sleep(0.2)

    if not await produto_selected_ok(stealth_server, instance_id, config.boletos_filter_scope_selector):
        produto_debug = await debug_collect_visible_texts(
            stealth_server,
            instance_id,
            f"{config.boletos_filter_scope_selector} *",
            35,
        )
        value_now = await get_filter_dropdown_value_text(
            stealth_server,
            instance_id,
            config.boletos_filter_scope_selector,
            0,
        )
        log("BOLETOS", f"Debug valor atual produto: '{value_now}'")
        log("BOLETOS", f"Debug elementos visiveis no filtro (produto): {produto_debug}")
        raise RuntimeError("Nao foi possivel confirmar a selecao da primeira opcao de Produto.")

    await save_screenshot(
        stealth_server,
        instance_id,
        build_screenshot_path(artifacts_dir, "06_boletos_produto"),
        "BOLETOS",
        "Screenshot apos selecionar Produto",
    )

    log("BOLETOS", f"Selecionando status '{config.boletos_status_option_text}'")
    opened_status = await open_status_dropdown_strict(
        stealth_server,
        instance_id,
        config.boletos_filter_scope_selector,
    )
    if not opened_status:
        opened_status = await click_by_selector_then_text_fallback(
            stealth_server,
            instance_id,
            config.boletos_status_trigger_selector,
            config.boletos_status_field_text,
        )
    if not opened_status:
        raise RuntimeError("Nao foi possivel abrir o filtro Status.")
    panel_open = await wait_for_open_options_panel(stealth_server, instance_id, timeout_seconds=5.0, poll_interval=0.2)
    if not panel_open:
        # Some implementations render options inside the same filter row, not overlay panels.
        if await select_status_option_in_scope(
            stealth_server,
            instance_id,
            config.boletos_filter_scope_selector,
            config.boletos_status_option_text,
        ):
            panel_open = True

    if not panel_open:
        scope_candidates = await debug_collect_visible_texts(
            stealth_server,
            instance_id,
            f"{config.boletos_filter_scope_selector} *",
            30,
        )
        log("BOLETOS", f"Debug elementos visiveis no filtro: {scope_candidates}")
        raise RuntimeError("Dropdown de Status nao abriu (painel sem opcoes).")

    if not await select_option_from_open_dropdown(stealth_server, instance_id, config.boletos_status_option_text):
        if not await click_text_anywhere(stealth_server, instance_id, config.boletos_status_option_text):
            candidates = await debug_collect_visible_texts(
                stealth_server,
                instance_id,
                '.ng-dropdown-panel .ng-option, [role="listbox"] [role="option"], .p-dropdown-panel .p-dropdown-item, .mat-select-panel .mat-option, li, [role="option"]',
                25,
            )
            log("BOLETOS", f"Debug opcoes visiveis (status): {candidates}")
            try:
                ok = await call_tool(
                    stealth_server,
                    "click_element",
                    instance_id=instance_id,
                    selector=config.boletos_results_option_selector,
                    text_match=config.boletos_status_option_text,
                    timeout=4000,
                )
                if not ok:
                    raise RuntimeError()
            except Exception:
                raise RuntimeError(f"Nao foi possivel selecionar o status '{config.boletos_status_option_text}'.")
    await asyncio.sleep(0.4)
    await save_screenshot(
        stealth_server,
        instance_id,
        build_screenshot_path(artifacts_dir, "07_boletos_status"),
        "BOLETOS",
        "Screenshot apos selecionar Status",
    )

    log("BOLETOS", "Clicando em BUSCAR")
    if not await click_by_selector_then_text_fallback(
        stealth_server,
        instance_id,
        config.boletos_buscar_selector,
        config.boletos_buscar_button_text,
    ):
        raise RuntimeError("Nao foi possivel clicar em BUSCAR.")
    await asyncio.sleep(0.4)
    await save_screenshot(
        stealth_server,
        instance_id,
        build_screenshot_path(artifacts_dir, "08_boletos_buscar"),
        "BOLETOS",
        "Screenshot apos BUSCAR",
    )

    log("BOLETOS", f"Alterando exibicao de resultados para '{config.boletos_results_target_text}'")
    _ = await click_by_selector_then_text_fallback(
        stealth_server,
        instance_id,
        config.boletos_results_trigger_selector,
        config.boletos_results_current_text,
    )
    await asyncio.sleep(0.5)
    if not await select_option_from_open_dropdown(stealth_server, instance_id, config.boletos_results_target_text):
        if not await click_text_anywhere(stealth_server, instance_id, config.boletos_results_target_text):
            candidates = await debug_collect_visible_texts(
                stealth_server,
                instance_id,
                '.ng-dropdown-panel .ng-option, [role="listbox"] [role="option"], .p-dropdown-panel .p-dropdown-item, .mat-select-panel .mat-option, li, [role="option"]',
                25,
            )
            log("BOLETOS", f"Debug opcoes visiveis (resultados): {candidates}")
            try:
                ok = await call_tool(
                    stealth_server,
                    "click_element",
                    instance_id=instance_id,
                    selector=config.boletos_results_option_selector,
                    text_match=config.boletos_results_target_text,
                    timeout=4000,
                )
                if not ok:
                    raise RuntimeError()
            except Exception:
                raise RuntimeError(f"Nao foi possivel selecionar '{config.boletos_results_target_text}'.")
    await asyncio.sleep(0.4)
    await save_screenshot(
        stealth_server,
        instance_id,
        build_screenshot_path(artifacts_dir, "09_boletos_50_resultados"),
        "BOLETOS",
        "Screenshot apos definir 50 resultados",
    )
    total_downloads = 0
    page_no = 1
    while True:
        links_count = await count_visible_text_clickables(
            stealth_server,
            instance_id,
            config.boletos_download_scope_selector,
            config.boletos_download_link_text,
        )
        if links_count <= 0:
            if page_no == 1:
                raise RuntimeError(
                    f"Nao encontrei links '{config.boletos_download_link_text}' na lista de boletos."
                )
            log("BOLETOS", f"Pagina {page_no}: nenhum link de boleto encontrado.")
        else:
            log(
                "BOLETOS",
                f"Pagina {page_no}: encontrados {links_count} links '{config.boletos_download_link_text}'. Iniciando downloads...",
            )
            for idx in range(links_count):
                before = snapshot_download_dir(download_dir)
                clicked = await click_visible_text_clickable_by_index(
                    stealth_server,
                    instance_id,
                    config.boletos_download_scope_selector,
                    config.boletos_download_link_text,
                    idx,
                )
                if not clicked:
                    raise RuntimeError(
                        f"Nao foi possivel clicar no link '{config.boletos_download_link_text}' "
                        f"(pagina {page_no}, indice {idx + 1}/{links_count})."
                    )
                downloaded = await wait_for_download_file(
                    download_dir=download_dir,
                    before=before,
                    timeout_seconds=float(config.boletos_download_timeout_seconds),
                    poll_interval=max(0.25, config.poll_interval_seconds),
                )
                if downloaded is None:
                    raise RuntimeError(
                        f"Timeout aguardando download do boleto {idx + 1}/{links_count} na pagina {page_no}."
                    )
                total_downloads += 1
                renamed = rename_download_with_timestamp(downloaded, total_downloads)
                log(
                    "BOLETOS",
                    f"Boleto {idx + 1}/{links_count} da pagina {page_no} baixado: {renamed.name}",
                )

        if page_no >= config.boletos_pagination_max_pages:
            log(
                "BOLETOS",
                f"Limite de paginas atingido ({config.boletos_pagination_max_pages}). Encerrando varredura.",
            )
            break

        next_page = page_no + 1
        clicked_next = await click_pagination_page_number(
            stealth_server,
            instance_id,
            config.boletos_pagination_scope_selector,
            next_page,
        )
        if not clicked_next:
            log("BOLETOS", f"Nao ha pagina {next_page} visivel. Encerrando downloads.")
            break
        moved = await wait_for_active_page(
            stealth_server,
            instance_id,
            config.boletos_pagination_scope_selector,
            next_page,
            timeout_seconds=float(config.boletos_pagination_timeout_seconds),
            poll_interval=max(0.25, config.poll_interval_seconds),
        )
        if not moved:
            log(
                "BOLETOS",
                f"Pagina {next_page} nao confirmou ativa no tempo esperado; continuando mesmo assim.",
            )
        await asyncio.sleep(0.4)
        await save_screenshot(
            stealth_server,
            instance_id,
            build_screenshot_path(artifacts_dir, f"10_boletos_page_{next_page}"),
            "BOLETOS",
            f"Screenshot apos ir para pagina {next_page}",
        )
        page_no = next_page

    await save_screenshot(
        stealth_server,
        instance_id,
        build_screenshot_path(artifacts_dir, "11_boletos_downloads"),
        "BOLETOS",
        "Screenshot apos baixar boletos",
    )
    log("BOLETOS", f"Fluxo de Baixar Boletos concluido com downloads. Total baixado: {total_downloads}")


async def command_loop(stealth_server, config: Config, instance_id: str, artifacts_dir: Path) -> None:
    log("HOLD", "Aguardando comandos via UI.")
    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if line == "":
            await asyncio.sleep(0.2)
            continue

        command = line.strip()
        if not command:
            continue

        if command == "CMD:EXIT":
            log("HOLD", "Recebido CMD:EXIT. Encerrando.")
            return

        if command.startswith("CMD:BAIXAR_BOLETOS|"):
            raw_dir = command.split("|", 1)[1].strip()
            if not raw_dir:
                log("BOLETOS", "Comando recebido sem diretorio. Ignorando.")
                continue
            try:
                await run_baixar_boletos_flow(
                    stealth_server=stealth_server,
                    config=config,
                    instance_id=instance_id,
                    artifacts_dir=artifacts_dir,
                    download_dir=Path(raw_dir),
                )
            except Exception as exc:
                log("BOLETOS", f"Falha no fluxo: {exc}")
            continue

        log("HOLD", f"Comando desconhecido: {command}")


async def run_flow(config: Config) -> None:
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    stealth_server = import_stealth_server(config.stealth_path)

    log("INIT", f"Stealth Browser MCP: {config.stealth_path}")
    log("INIT", f"Modo: {'background-headed' if config.background_headed else 'headed'}")
    log("INIT", f"Background headed (Xvfb): {config.background_headed}")
    log("INIT", f"Sandbox: {config.sandbox}")
    log("INIT", f"User data dir: {config.user_data_dir}")

    instance = await call_tool(
        stealth_server,
        "spawn_browser",
        headless=False,
        sandbox=config.sandbox,
        user_data_dir=config.user_data_dir,
    )
    instance_id = instance["instance_id"]
    log("BROWSER", f"Instancia criada: {instance_id}")

    try:
        if config.resume_session:
            log("RESUME", "Retomando sessao salva a partir do dashboard")
            await call_tool(
                stealth_server,
                "navigate",
                instance_id=instance_id,
                url=config.dashboard_url,
            )
            log("RESUME", "Validando rota funcional do dashboard")
            try:
                await wait_for_url_contains(
                    stealth_server=stealth_server,
                    instance_id=instance_id,
                    fragment=config.dashboard_path_fragment,
                    timeout_seconds=config.dashboard_timeout_seconds,
                    poll_interval=config.poll_interval_seconds,
                )
                log("RESUME", "Rota do dashboard validada")
            except TimeoutError:
                log("RESUME", "Rota esperada nao confirmada dentro do timeout; seguindo com validacao por texto")
            log("RESUME", f"Revalidando STEP-5 por texto: '{config.post_auth_validation_text}'")
            await wait_for_text(
                stealth_server=stealth_server,
                instance_id=instance_id,
                expected_text=config.post_auth_validation_text,
                timeout_seconds=config.dashboard_timeout_seconds,
                poll_interval=config.poll_interval_seconds,
            )
            log("RESUME", "Sessao validada no dashboard")
            await save_screenshot(
                stealth_server,
                instance_id,
                build_screenshot_path(artifacts_dir, "04_resume_dashboard"),
                "RESUME",
                "Screenshot do dashboard retomado",
            )
            log("RESUME", "Retomada concluida; seguindo fluxo pos-sessao.")
            log("RESUME", f"Screenshots salvos em: {artifacts_dir.resolve()}")
            if config.keep_browser_open:
                await command_loop(stealth_server, config, instance_id, artifacts_dir)
            return

        log("STEP-1", "Navegando para URL de login configurada")
        nav = await call_tool(stealth_server, "navigate", instance_id=instance_id, url=config.login_url)
        initial_url = nav.get("url") or config.login_url
        log("STEP-1", "Navegacao inicial concluida")

        log("STEP-1", "Aguardando redirect e validacao de texto da pagina...")
        await wait_for_redirect(
            stealth_server=stealth_server,
            instance_id=instance_id,
            initial_url=initial_url,
            expected_text=config.redirect_validation_text,
            timeout_seconds=config.redirect_timeout_seconds,
            poll_interval=config.poll_interval_seconds,
        )
        log("STEP-1", "Redirect confirmado")

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

        await save_screenshot(
            stealth_server,
            instance_id,
            build_screenshot_path(artifacts_dir, "01_before_entrar"),
            "STEP-2",
            "Salvando screenshot antes do click",
        )

        log("STEP-3", "Clicando no botao ENTRAR")
        await call_tool(
            stealth_server,
            "click_element",
            instance_id=instance_id,
            selector=config.entrar_selector,
            text_match=config.entrar_text,
        )

        await save_screenshot(
            stealth_server,
            instance_id,
            build_screenshot_path(artifacts_dir, "02_after_entrar"),
            "STEP-3",
            "Salvando screenshot apos click",
        )

        await validate_text_if_configured(
            stealth_server=stealth_server,
            instance_id=instance_id,
            expected_text=config.post_login_validation_text,
            timeout_seconds=config.post_login_timeout_seconds,
            poll_interval=config.poll_interval_seconds,
            step="STEP-3",
            wait_message="Aguardando texto de validacao pos-login",
            ok_message="Validacao pos-login OK",
        )

        if config.receive_code_text:
            log("STEP-4", f"Clicando no botao: '{config.receive_code_text}'")
            await call_tool(
                stealth_server,
                "click_element",
                instance_id=instance_id,
                selector=config.receive_code_selector,
                text_match=config.receive_code_text,
            )

            await save_screenshot(
                stealth_server,
                instance_id,
                build_screenshot_path(artifacts_dir, "03_after_receive_code_click"),
                "STEP-4",
                "Salvando screenshot apos click em receber codigo",
            )

            if config.receive_code_validation_text:
                await validate_text_if_configured(
                    stealth_server=stealth_server,
                    instance_id=instance_id,
                    expected_text=config.receive_code_validation_text,
                    timeout_seconds=config.receive_code_timeout_seconds,
                    poll_interval=config.poll_interval_seconds,
                    step="STEP-4",
                    wait_message="Aguardando texto de validacao apos receber codigo",
                    ok_message="Validacao apos receber codigo OK",
                )
                log("STEP-5", f"Informe o OTP no console. Campo alvo: {config.otp_input_selector}")
                otp_code = await asyncio.to_thread(input, "Digite o codigo OTP recebido por e-mail: ")
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

                await save_screenshot(
                    stealth_server,
                    instance_id,
                    build_screenshot_path(artifacts_dir, "04_after_authenticate_click"),
                    "STEP-5",
                    "Salvando screenshot apos click em autenticar",
                )

                await validate_text_if_configured(
                    stealth_server=stealth_server,
                    instance_id=instance_id,
                    expected_text=config.post_auth_validation_text,
                    timeout_seconds=config.post_auth_timeout_seconds,
                    poll_interval=config.poll_interval_seconds,
                    step="STEP-5",
                    wait_message="Aguardando texto de validacao pos-autenticacao",
                    ok_message="Validacao pos-autenticacao OK",
                )

        log("DONE", "Fluxo concluido com sucesso.")
        log("DONE", f"Screenshots salvos em: {artifacts_dir.resolve()}")

        if config.keep_browser_open:
            await command_loop(stealth_server, config, instance_id, artifacts_dir)

    except KeyboardInterrupt:
        log("EXIT", "Interrompido pelo usuario.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fluxo de login com stealth-browser-mcp")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--headed", action="store_true", help="Forca modo headed")
    mode.add_argument("--background-headed", action="store_true", help="Executa headed em background via Xvfb")
    parser.add_argument("--resume-session", action="store_true", help="Retoma sessao salva a partir do dashboard")
    parser.add_argument("--no-keep-open", action="store_true", help="Nao manter o navegador aberto ao final")
    return parser.parse_args()


def ensure_xvfb_background(config: Config) -> None:
    if not config.background_headed:
        return

    if os.environ.get("STEALTH_XVFB_ACTIVE") == "1":
        return

    if not shutil.which("xvfb-run"):
        raise RuntimeError(
            "BACKGROUND_HEADED/--background-headed requer xvfb-run instalado. "
            "Instale com: sudo apt-get update && sudo apt-get install -y xvfb"
        )

    cmd = ["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24", sys.executable, Path(__file__).resolve().as_posix()]
    cmd.extend(sys.argv[1:])
    env = os.environ.copy()
    env["STEALTH_XVFB_ACTIVE"] = "1"
    log("INIT", "Relancando processo em Xvfb para rodar headed em background")
    os.execvpe(cmd[0], cmd, env)


def main() -> None:
    args = parse_args()
    config = build_config(args)
    ensure_xvfb_background(config)
    asyncio.run(run_flow(config))


if __name__ == "__main__":
    main()
