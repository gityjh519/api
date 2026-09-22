from fastapi import FastAPI,File,UploadFile,Depends,HTTPException,status
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
import os
import shutil

from test import BibleAddBody

# 1. 创建SQLite数据库文件（会自动生成 bible.db 在项目文件夹）
SQLALCHEMY_DATABASE_URL = "sqlite:///./bible.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. 定义数据库表结构（和你iOS字段对齐：卷、章、节、内容）
class BibleModel(Base):
    __tablename__ = "bible"
    id = Column(Integer, primary_key=True, index=True)
    volumIndex = Column(Integer)
    chapterIndex = Column(Integer)
    sectionIndex = Column(Integer)
    content = Column(String)

# 创建数据表（不存在就自动新建表）
Base.metadata.create_all(bind=engine)

# 3. FastAPI实例
app = FastAPI(title="圣经接口服务")

# 获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===================== 接口1：新增一条经文数据（插入数据库） =====================
from fastapi import Depends
from sqlalchemy.orm import Session

def add_bible(volumIndex:int, chapterIndex:int, sectionIndex:int, content:str, db:Session = Depends(get_db)):
    new_row = BibleModel(
        volumIndex=volumIndex,
        chapterIndex=chapterIndex,
        sectionIndex=sectionIndex,
        content=content
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return {"code":200, "msg":"插入成功", "data":new_row}


@app.post("/api/bible/add_body")
def add_bible_content(body: BibleAddBody,db: Session = Depends(get_db)):
   return add_bible(body.volumIndex, body.chapterIndex, body.sectionIndex, body.content, db)

# ===================== 接口2：查询经文（你App调用的GET接口） =====================
@app.get("/api/bible")
def get_bible(volumIndex:int, chapterIndex:int, sectionIndex:int, db:Session = Depends(get_db)):
    # 根据三个字段查询单条记录
    result = db.query(BibleModel).filter(
        BibleModel.volumIndex == volumIndex,
        BibleModel.chapterIndex == chapterIndex,
        BibleModel.sectionIndex == sectionIndex
    ).all()[1]
    if not result:
        return {"code":404, "msg":"没有找到经文"}
    return {
        "code": 200,
        "msg": "success",
        "volumIndex": result.volumIndex,
        "chapterIndex": result.chapterIndex,
        "sectionIndex": result.sectionIndex,
        "content": result.content
    }

UPLOAD_FOLDER = "upload_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.post("/api/upload/image",description="这个是上传图片具体方法",summary="这个是上传图片")
async def upload_image(file: UploadFile = File(...)):
    content_type = file.content_type
    if not content_type or content_type.startswith("image/",None):
        return {"code": 400,"msg": "只能上传图片"}
    filename = file.filename
    if not filename:
        return {"code": 400, "msg": "只能上传图片"}
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    with open(save_path,"wb") as f:
        while chunk := await file.read(8192):
            f.write(chunk)

    return {"code":200, "msg":"图片上传成功", "name":file.filename}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
