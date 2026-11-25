"""
Resolución de la IP real del cliente detrás de Vercel + balanceador de Render (P1.7).

Cadena de producción: navegador -> Vercel (rewrite /api/*) -> balanceador de Render -> uvicorn.
Render añade a X-Forwarded-For la IP que se le conectó; Vercel pone la IP del visitante y además
la cabecera secreta X-Proxy-Secret. El par TCP que ve la app es una IP interna del balanceador.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from backend.rate_limits import get_client_ip, check_auth_rate_limit, auth_attempts

RENDER_LB = "10.204.3.7"        # IP interna del balanceador de Render (par TCP)
VERCEL_EGRESS = "76.76.21.21"   # IP de salida de Vercel
ALICE = "198.51.100.10"
BOB = "198.51.100.20"
ATTACKER = "203.0.113.66"
SECRET = "s3cr3t-de-prueba-largo"

RENDER_ENV = {
    "FORWARDED_ALLOW_IPS": "127.0.0.1,::1",
    "TRUSTED_PROXY_HOPS": "1",
    "PROXY_SHARED_SECRET": SECRET,
}


def make_request(peer, xff=None, secret=None, real_ip=None):
    req = MagicMock()
    req.client.host = peer
    headers = {}
    if xff is not None:
        headers["X-Forwarded-For"] = xff
    if secret is not None:
        headers["X-Proxy-Secret"] = secret
    if real_ip is not None:
        headers["X-Real-IP"] = real_ip
    req.headers = headers
    return req


@pytest.fixture
def render_env():
    with patch.dict(os.environ, RENDER_ENV):
        yield


# --- Sin proxies (desarrollo / pruebas) -------------------------------------------------------

def test_sin_proxy_usa_el_par_e_ignora_cabeceras():
    req = make_request(ATTACKER, xff="1.1.1.1", real_ip="2.2.2.2")
    assert get_client_ip(req) == ATTACKER


def test_sin_client_usa_loopback():
    req = MagicMock()
    req.client = None
    req.headers = {}
    assert get_client_ip(req) == "127.0.0.1"


# --- Producción: a través de Vercel -----------------------------------------------------------

def test_via_vercel_con_secreto_devuelve_ip_del_visitante(render_env):
    req = make_request(RENDER_LB, xff=f"{ALICE}, {VERCEL_EGRESS}", secret=SECRET)
    assert get_client_ip(req) == ALICE


def test_via_vercel_usuarios_distintos_no_comparten_ip(render_env):
    a = make_request(RENDER_LB, xff=f"{ALICE}, {VERCEL_EGRESS}", secret=SECRET)
    b = make_request(RENDER_LB, xff=f"{BOB}, {VERCEL_EGRESS}", secret=SECRET)
    assert get_client_ip(a) != get_client_ip(b)


def test_via_vercel_aunque_vercel_anexe_no_se_acepta_la_ip_inyectada(render_env):
    """Si Vercel añadiera en vez de sobrescribir, la entrada inyectada queda a la izquierda."""
    req = make_request(RENDER_LB, xff=f"6.6.6.6, {ALICE}, {VERCEL_EGRESS}", secret=SECRET)
    assert get_client_ip(req) == ALICE


def test_rotacion_de_secreto_acepta_ambos_valores():
    with patch.dict(os.environ, {**RENDER_ENV, "PROXY_SHARED_SECRET": f"viejo-valor, {SECRET}"}):
        for value in ("viejo-valor", SECRET):
            req = make_request(RENDER_LB, xff=f"{ALICE}, {VERCEL_EGRESS}", secret=value)
            assert get_client_ip(req) == ALICE


# --- Producción: llamando directo a reeftrack-api.onrender.com --------------------------------

def test_directo_no_puede_falsificar_xff(render_env):
    """El atacante manda XFF falso; Render añade su IP real a la derecha."""
    req = make_request(RENDER_LB, xff=f"{ALICE}, {VERCEL_EGRESS}, {ATTACKER}")
    assert get_client_ip(req) == ATTACKER


def test_directo_con_secreto_incorrecto_no_gana_el_salto_extra(render_env):
    req = make_request(RENDER_LB, xff=f"{ALICE}, {ATTACKER}", secret="adivinado")
    assert get_client_ip(req) == ATTACKER


def test_directo_no_puede_falsificar_x_real_ip(render_env):
    req = make_request(RENDER_LB, xff=ATTACKER, real_ip=ALICE)
    assert get_client_ip(req) == ATTACKER


def test_secreto_sin_configurar_no_confia_en_cualquier_cabecera():
    with patch.dict(os.environ, {**RENDER_ENV, "PROXY_SHARED_SECRET": ""}):
        req = make_request(RENDER_LB, xff=f"{ALICE}, {ATTACKER}", secret="")
        assert get_client_ip(req) == ATTACKER


def test_sin_hops_el_secreto_no_basta():
    """El secreto suma un salto a TRUSTED_PROXY_HOPS; con 0 hops no se activa por sí solo."""
    with patch.dict(os.environ, {**RENDER_ENV, "TRUSTED_PROXY_HOPS": "0"}):
        req = make_request(ATTACKER, xff=ALICE, secret=SECRET)
        assert get_client_ip(req) == ATTACKER


# --- Casos límite -----------------------------------------------------------------------------

def test_xff_mas_corto_que_los_hops_no_sale_de_la_cadena(render_env):
    req = make_request(RENDER_LB, xff=ALICE, secret=SECRET)
    assert get_client_ip(req) == ALICE


def test_entrada_ilegible_cae_al_par(render_env):
    req = make_request(RENDER_LB, xff="no-es-una-ip")
    assert get_client_ip(req) == RENDER_LB


def test_entradas_con_puerto_e_ipv6(render_env):
    assert get_client_ip(make_request(RENDER_LB, xff=f"{ALICE}:51234")) == ALICE
    assert get_client_ip(make_request(RENDER_LB, xff="[2001:db8::1]:443")) == "2001:db8::1"


def test_forwarded_allow_ips_admite_cidr():
    with patch.dict(os.environ, {"FORWARDED_ALLOW_IPS": "10.0.0.0/8", "TRUSTED_PROXY_HOPS": "0"}):
        req = make_request(RENDER_LB, xff=f"6.6.6.6, {ALICE}, 10.1.2.3")
        assert get_client_ip(req) == ALICE


def test_forwarded_allow_ips_comodin_conserva_comportamiento_de_uvicorn():
    """'*' confía en todo y devuelve la primera entrada: solo apto para desarrollo."""
    with patch.dict(os.environ, {"FORWARDED_ALLOW_IPS": "*", "TRUSTED_PROXY_HOPS": "0"}):
        req = make_request(ATTACKER, xff=f"{ALICE}, 10.0.0.1")
        assert get_client_ip(req) == ALICE


# --- Integración con el rate limit de autenticación ------------------------------------------

def test_rate_limit_de_login_es_por_visitante_y_no_global(render_env):
    """5 intentos de Alice no bloquean a Bob aunque ambos lleguen por el mismo balanceador."""
    from fastapi import HTTPException

    auth_attempts.clear()
    try:
        for _ in range(5):
            check_auth_rate_limit(make_request(RENDER_LB, xff=f"{ALICE}, {VERCEL_EGRESS}", secret=SECRET))
        with pytest.raises(HTTPException) as exc:
            check_auth_rate_limit(make_request(RENDER_LB, xff=f"{ALICE}, {VERCEL_EGRESS}", secret=SECRET))
        assert exc.value.status_code == 429

        # Bob sigue pudiendo intentar
        check_auth_rate_limit(make_request(RENDER_LB, xff=f"{BOB}, {VERCEL_EGRESS}", secret=SECRET))
    finally:
        auth_attempts.clear()
