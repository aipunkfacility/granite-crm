from fastapi import APIRouter

from server.models import TemplateUpdate

router = APIRouter(prefix="/template", tags=["template"])


@router.get("")
async def get_template():
    from server.config import template_html

    return {"html": template_html}


@router.post("")
async def update_template(body: TemplateUpdate):
    import os
    from server.config import config, template_html

    template_path = os.path.join(
        config.get("BASE_DIR", ""), config.get("template_file", "email_template.html")
    )
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(body.html)

    return {"success": True, "message": "Template updated"}
