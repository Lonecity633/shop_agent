from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_backend_exposes_product_order_and_policy_routes():
    product_router = (ROOT / "app/backend/api/public/routers/product.py").read_text(encoding="utf-8")
    order_router = (ROOT / "app/backend/api/public/routers/order.py").read_text(encoding="utf-8")
    internal_tools = (ROOT / "app/backend/api/internal_tools.py").read_text(encoding="utf-8")

    assert 'APIRouter(prefix="/products"' in product_router
    assert '@router.get("/{order_no}"' in order_router
    assert '@router.get("/knowledge/policies/search")' in internal_tools


def test_backend_entrypoint_does_not_expose_agent_chat():
    backend_main = (ROOT / "app/backend/main.py").read_text(encoding="utf-8")
    assert "/agent/chat" not in backend_main
