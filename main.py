import os
import sys
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# 假设你的 test.py 里面定义了 BibleAddBody，这里保持原样
try:
    from test import BibleAddBody
except ImportError:
    class BibleAddBody(BaseModel):
        volumIndex: int
        chapterIndex: int
        sectionIndex: int
        content: str

# =========================================================================
# 🚀 核心重构：环境智能嗅探（环境双轨制，完美消灭 cell_runtime 和 workers 找不到的红线）
# =========================================================================
IS_CLOUDFLARE = False

try:
    from workers import asgi
    import cell_runtime

    IS_CLOUDFLARE = True
    print("☁️ 检测到 Cloudflare 生产环境，已成功挂载云端异步流水线")
except ImportError:
    print("💻 检测到本地开发环境，自动降级为本地 SQLite + SQLAlchemy 引擎")

# 1. 如果是本地开发环境，初始化你原汁原味的本地 SQLite
if not IS_CLOUDFLARE:
    SQLALCHEMY_DATABASE_URL = "sqlite:///./bible.db"
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()


    class BibleModel(Base):
        __tablename__ = "bible"
        id = Column(Integer, primary_key=True, index=True)
        volumIndex = Column(Integer)
        chapterIndex = Column(Integer)
        sectionIndex = Column(Integer)
        content = Column(String)


    Base.metadata.create_all(bind=engine)


    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

# 2. 初始化 FastAPI 实例
app = FastAPI(title="圣经接口服务")


# ===================== 接口1：新增一条经文数据 =====================
@app.post("/api/bible/add_body")
async def add_bible_content(body: BibleAddBody):
    if IS_CLOUDFLARE:
        # ☁️ 线上分支：直接调用 wrangler.toml 绑定的 D1 数据库执行纯 SQL
        from cell_runtime import env  # type: ignore
        db = env.DB
        await db.exec("""
            CREATE TABLE IF NOT EXISTS bible (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                volumIndex INTEGER,
                chapterIndex INTEGER,
                sectionIndex INTEGER,
                content TEXT
            )
        """)
        await db.prepare(
            "INSERT INTO bible (volumIndex, chapterIndex, sectionIndex, content) VALUES (?, ?, ?, ?)"
        ).bind(body.volumIndex, body.chapterIndex, body.sectionIndex, body.content).run()
        return {"code": 200, "msg": "线上D1插入成功", "data": body}
    else:
        # 💻 本地分支：调用原生的 SQLAlchemy 插入本地 bible.db 文件
        db: Session = next(get_db())
        new_row = BibleModel(
            volumIndex=body.volumIndex,
            chapterIndex=body.chapterIndex,
            sectionIndex=body.sectionIndex,
            content=body.content
        )
        db.add(new_row)
        db.commit()
        db.refresh(new_row)
        return {"code": 200, "msg": "本地SQLite插入成功", "data": {"id": new_row.id}}


# ===================== 接口2：查询经文（App调用的GET接口） =====================
@app.get("/api/bible")
async def get_bible(volumIndex: int, chapterIndex: int, sectionIndex: int):
    if IS_CLOUDFLARE:
        # ☁️ 线上分支：查询线上 D1
        from cell_runtime import env  # type: ignore
        db = env.DB
        result = await db.prepare(
            "SELECT * FROM bible WHERE volumIndex = ? AND chapterIndex = ? AND sectionIndex = ?"
        ).bind(volumIndex, chapterIndex, sectionIndex).first()

        if not result:
            return {"code": 404, "msg": "没有找到经文"}
        return {
            "code": 200,
            "msg": "success",
            "volumIndex": result["volumIndex"],
            "chapterIndex": result["chapterIndex"],
            "sectionIndex": result["sectionIndex"],
            "content": result["content"]
        }
    else:
        # 💻 本地分支：查询本地 SQLite
        db: Session = next(get_db())
        result = db.query(BibleModel).filter(
            BibleModel.volumIndex == volumIndex,
            BibleModel.chapterIndex == chapterIndex,
            BibleModel.sectionIndex == sectionIndex
        ).first()

        if not result:
            return {"code": 404, "msg": "没有找到经文"}
        return {
            "code": 200,
            "msg": "success",
            "volumIndex": result.volumIndex,
            "chapterIndex": result.chapterIndex,
            "sectionIndex": result.sectionIndex,
            "content": result.content
        }


# ===================== 接口3：图片上传 =====================
UPLOAD_FOLDER = "upload_images"

#
# @app.post("/api/upload/image", description="上传图片")
# async def upload_image(file: UploadFile = File(...)):
#     content_type = file.content_type
#     if not content_type or not content_type.startswith("image/"):
#         return {"code": 400, "msg": "只能上传图片"}
#
#     filename = file.filename
#     if not filename:
#         return {"code": 400, "msg": "文件名无效"}
#
#     file_bytes = await file.read()
#
#     if IS_CLOUDFLARE:
#         # ☁️ 线上分支：写入云端免费 R2 存储桶
#         from cell_runtime import env  # type: ignore
#         bucket = env.BUCKET
#         await bucket.put(filename, file_bytes)
#         return {"code": 200, "msg": "线上R2图片上传成功", "name": filename}
#     else:
#         # 💻 本地分支：直接保存到本地物理文件夹
#         os.makedirs(UPLOAD_FOLDER, exist_ok=True)
#         save_path = os.path.join(UPLOAD_FOLDER, filename)
#         with open(save_path, "wb") as f:
#             f.write(file_bytes)
#         return {"code": 200, "msg": "本地物理图片上传成功", "name": filename}
#

# =========================================================================
# 🚀 优雅出口：线上绑定云端网关，本地挂载 uvicorn 监听
# =========================================================================
if IS_CLOUDFLARE:
    from workers import asgi  # type: ignore

    Default = asgi.entrypoint(app)
else:
    if __name__ == "__main__":
        import uvicorn

        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
