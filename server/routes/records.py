"""历史记录路由：列表/回看/保存/删除/清空。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..deps import get_vault
from ..schemas import RecordOut, SaveRecordRequest, SaveRecordResponse

router = APIRouter()


@router.get("", response_model=list[RecordOut])
def list_records():
    return [RecordOut(**r) for r in get_vault().list_records()]


@router.get("/{rid}")
def get_record(rid: str):
    content = get_vault().load(rid)
    if content is None:
        raise HTTPException(404, "记录不存在")
    return {"id": rid, "content": content}


@router.post("", response_model=SaveRecordResponse)
def save_record(req: SaveRecordRequest):
    rid = get_vault().save(req.name, req.content, req.kind)
    return SaveRecordResponse(id=rid, message=f"已加密保存（id={rid}）")


@router.delete("/{rid}")
def delete_record(rid: str):
    ok = get_vault().delete(rid)
    if not ok:
        raise HTTPException(404, "记录不存在")
    return {"message": f"已删除 {rid}"}


@router.delete("")
def wipe_records():
    get_vault().wipe_all()
    return {"message": "已清空全部本地数据（不可恢复）"}
