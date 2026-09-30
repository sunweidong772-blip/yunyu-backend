"""云屿 FastApp 完整后端 - FastAPI + SQLite"""
import os, time, json, sqlite3, hashlib, secrets, uuid
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

DB = "yunyu.db"
app = FastAPI(title="云屿API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        uid INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, mail TEXT UNIQUE,
        password TEXT, token TEXT DEFAULT '', created INTEGER,
        coins INTEGER DEFAULT 100, vip INTEGER DEFAULT 0, vipExpire INTEGER DEFAULT 0,
        avatar TEXT DEFAULT '', "group" TEXT DEFAULT 'subscriber',
        intro TEXT DEFAULT '', experience INTEGER DEFAULT 0, status INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS contents(
        cid INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, text TEXT,
        created INTEGER, modified INTEGER, authorId INTEGER DEFAULT 1,
        type TEXT DEFAULT 'post', status TEXT DEFAULT 'publish',
        commentsNum INTEGER DEFAULT 0, views INTEGER DEFAULT 0, likes INTEGER DEFAULT 0,
        abcimg TEXT DEFAULT '', price INTEGER DEFAULT 0, isTop INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS comments(
        coid INTEGER PRIMARY KEY AUTOINCREMENT, cid INTEGER, authorId INTEGER,
        text TEXT, created INTEGER, authorName TEXT DEFAULT '', status INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS metas(
        mid INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, slug TEXT,
        type TEXT DEFAULT 'category', description TEXT DEFAULT '', orderNum INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS relationships(cid INTEGER, mid INTEGER);
    CREATE TABLE IF NOT EXISTS likes(uid INTEGER, cid INTEGER, type TEXT DEFAULT 'like', created INTEGER, PRIMARY KEY(uid,cid,type));
    CREATE TABLE IF NOT EXISTS follows(uid INTEGER, fanId INTEGER, created INTEGER, PRIMARY KEY(uid,fanId));
    CREATE TABLE IF NOT EXISTS shops(sid INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, price INTEGER, image TEXT DEFAULT '', typeId INTEGER DEFAULT 0, stock INTEGER DEFAULT 99, sales INTEGER DEFAULT 0, status INTEGER DEFAULT 1, created INTEGER);
    CREATE TABLE IF NOT EXISTS shop_types(tid INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
    CREATE TABLE IF NOT EXISTS orders(oid INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, sid INTEGER, price INTEGER, status INTEGER DEFAULT 0, created INTEGER);
    CREATE TABLE IF NOT EXISTS signs(sid INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, created INTEGER, reward INTEGER DEFAULT 10, UNIQUE(uid,created));
    CREATE TABLE IF NOT EXISTS chats(cgid INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, type TEXT DEFAULT 'private', ownerId INTEGER, created INTEGER);
    CREATE TABLE IF NOT EXISTS chat_msgs(mid INTEGER PRIMARY KEY AUTOINCREMENT, cgid INTEGER, senderId INTEGER, text TEXT, created INTEGER);
    CREATE TABLE IF NOT EXISTS inbox(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, title TEXT, content TEXT, created INTEGER, isRead INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS activities(aid INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, status INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS ads(aid INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, image TEXT, type TEXT DEFAULT 'banner', status INTEGER DEFAULT 1, sort INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS spaces(spid INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, created INTEGER);
    CREATE TABLE IF NOT EXISTS finances(fid INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, amount INTEGER, type TEXT, remark TEXT, created INTEGER);
    """)
    c.commit()
    if not c.execute("SELECT 1 FROM users WHERE uid=1").fetchone():
        pw = hashlib.md5(b"admin123").hexdigest()
        c.execute('INSERT INTO users(name,mail,password,created,"group",coins,experience) VALUES(?,?,?,?,?,?,?)',
                  ("admin","admin@yunyu.com",pw,int(time.time()),"administrator",99999,99999))
    if not c.execute("SELECT 1 FROM metas LIMIT 1").fetchone():
        for i,(n,s) in enumerate([("技术交流","tech"),("生活分享","life"),("问答求助","qa"),("公告","notice")]):
            c.execute("INSERT INTO metas(name,slug,type,orderNum) VALUES(?,?,?,?)",(n,s,"category",i))
    if not c.execute("SELECT 1 FROM ads LIMIT 1").fetchone():
        for i in range(5):
            c.execute("INSERT INTO ads(title,image,type,sort) VALUES(?,?,?,?)",(f"banner{i+1}",f"https://picsum.photos/seed/b{i}/750/300.jpg","banner",i))
    if not c.execute("SELECT 1 FROM shops LIMIT 1").fetchone():
        c.execute("INSERT INTO shop_types(name) VALUES('虚拟商品')")
        for i in range(5):
            c.execute("INSERT INTO shops(name,description,price,image,typeId,created) VALUES(?,?,?,?,?,?)",
                     (f"虚拟商品{i+1}","描述",10*(i+1),f"https://picsum.photos/seed/s{i}/200/200.jpg",1,int(time.time())))
    if not c.execute("SELECT 1 FROM contents LIMIT 1").fetchone():
        import random
        now=int(time.time())
        samples=[("欢迎来到云屿","<p>欢迎来到云屿社区！</p><p>你可以浏览文章、发布动态、评论互动、签到领金币。</p>",1),
                 ("如何发布文章","<p>点击底部+号发布文章，支持Markdown。</p>",1),
                 ("社区规则","<p>1.文明发言 2.禁止广告 3.尊重他人</p>",4),
                 ("FastAPI入门","<p>FastAPI是现代快速的Python Web框架。</p>",1),
                 ("生活随笔","<p>分享一些生活小确幸。</p>",2),
                 ("常见问题","<p>Q:如何注册？A:点击注册即可。</p>",3)]
        for i,(t,x,mid) in enumerate(samples):
            c.execute("INSERT INTO contents(title,text,created,modified,abcimg,commentsNum,views) VALUES(?,?,?,?,?,?,?)",
                     (t,x,now-i*3600*5,now-i*3600*5,f"https://picsum.photos/seed/{i}/800/400.jpg",random.randint(0,50),random.randint(100,9999)))
            c.execute("INSERT INTO relationships(cid,mid) VALUES(?,?)",(i+1,mid))
        for i in range(3):
            c.execute("INSERT INTO comments(cid,authorId,text,created,authorName) VALUES(?,?,?,?,?)",(1,1,f"评论{i+1}：说得好！",now-i*600,"admin"))
    c.commit()
    c.close()

init_db()

def ok(d=None): return {"code":1,"data":d if d is not None else {}}
def fail(m="操作失败"): return {"code":0,"msg":m}

def get_uid(token):
    if not token: return 0
    r=db().execute("SELECT uid FROM users WHERE token=? AND status=0",(token,)).fetchone()
    return r["uid"] if r else 0

def get_user(uid):
    return db().execute('SELECT uid,name,mail,coins,vip,vipExpire,avatar,"group",intro,experience FROM users WHERE uid=?',(uid,)).fetchone() if uid else None

def build_content(row, uid=0):
    d=dict(row); c=db()
    d["fields"]=[{"name":"abcimg","strValue":d.get("abcimg","")}]
    u=c.execute("SELECT name,avatar,\"group\",experience,vip FROM users WHERE uid=?",(d["authorId"],)).fetchone()
    au={"uid":d["authorId"],"name":u["name"] if u else "admin",
        "avatar":u["avatar"] if u else "","isvip":u["vip"] if u else 0,
        "experience":u["experience"] if u else 0,"group":u["group"] if u else "subscriber",
        "screenNamecolor":"","customize":"","customizecolor":""}
    d["authorInfo"]=au
    d["author"]=au
    # images array
    img=d.get("abcimg","")
    d["images"]=[img] if img else []
    # category
    cats=c.execute("SELECT m.mid,m.name FROM relationships r JOIN metas m ON r.mid=m.mid WHERE r.cid=?",(d["cid"],)).fetchall()
    d["category"]=[{"mid":r["mid"],"name":r["name"]} for r in cats]
    if uid:
        d["isLike"]=1 if c.execute("SELECT 1 FROM likes WHERE uid=? AND cid=? AND type='like'",(uid,d["cid"])).fetchone() else 0
        d["isMark"]=1 if c.execute("SELECT 1 FROM likes WHERE uid=? AND cid=? AND type='mark'",(uid,d["cid"])).fetchone() else 0
    else: d["isLike"]=0; d["isMark"]=0
    return d

async def form(req):
    d = dict(await req.form())
    if "params" in d:
        try:
            d.update(json.loads(d["params"]))
        except: pass
    return d

# ===== 用户 =====
@app.post("/typechoUsers/userLogin")
async def login(req: Request):
    f=await form(req); u=db().execute("SELECT * FROM users WHERE (name=? OR mail=?) AND password=? AND status=0",
        (f.get("name",""),f.get("name",""),hashlib.md5(f.get("password","").encode()).hexdigest())).fetchone()
    if not u: return fail("用户名或密码错误")
    token=secrets.token_hex(16); c=db(); c.execute("UPDATE users SET token=? WHERE uid=?",(token,u["uid"])); c.commit()
    return ok({"uid":u["uid"],"name":u["name"],"token":token,"coins":u["coins"],"vip":u["vip"],"avatar":u["avatar"],"group":u["group"],"mail":u["mail"],"experience":u["experience"]})

@app.post("/typechoUsers/userRegister")
async def register(req: Request):
    f=await form(req); c=db()
    try:
        c.execute("INSERT INTO users(name,mail,password,created) VALUES(?,?,?,?)",
                  (f.get("name",""),f.get("mail",""),hashlib.md5(f.get("password","").encode()).hexdigest(),int(time.time())))
        c.commit()
    except: return fail("用户名或邮箱已存在")
    return ok({})

@app.post("/typechoUsers/RegSendCode")
@app.post("/typechoUsers/SendCode")
@app.post("/typechoUsers/FogetSendCode")
async def send_code(req: Request): return ok({})

@app.post("/typechoUsers/userFoget")
async def forget(req: Request):
    f=await form(req); c=db(); c.execute("UPDATE users SET password=? WHERE mail=?",(hashlib.md5(f.get("password","").encode()).hexdigest(),f.get("mail",""))); c.commit(); return ok({})

@app.get("/typechoUsers/userInfo")
def user_info(token: str=""):
    uid=get_uid(token)
    if not uid: return fail("请先登录")
    d=dict(get_user(uid))
    d["followCount"]=db().execute("SELECT COUNT(*) c FROM follows WHERE uid=?",(uid,)).fetchone()["c"]
    d["fanCount"]=db().execute("SELECT COUNT(*) c FROM follows WHERE fanId=?",(uid,)).fetchone()["c"]
    return ok(d)

@app.get("/typechoUsers/userData")
def user_data(uid: int=0):
    u=get_user(uid); return ok(dict(u) if u else {})

@app.get("/typechoUsers/userList")
def user_list(page: int=1, limit: int=20):
    off=(page-1)*limit
    return ok([dict(r) for r in db().execute('SELECT uid,name,avatar,"group",created FROM users ORDER BY uid LIMIT ? OFFSET ?',(limit,off)).fetchall()])

@app.post("/typechoUsers/userEdit")
async def user_edit(req: Request):
    f=await form(req); uid=get_uid(f.get("token",""))
    if not uid: return fail("请先登录")
    c=db()
    for k in ("name","intro","avatar"):
        if f.get(k): c.execute(f"UPDATE users SET {k}=? WHERE uid=?",(f[k],uid))
    c.commit(); return ok({})

@app.post("/typechoUsers/signOut")
async def signout(req: Request):
    f=await form(req); c=db(); c.execute("UPDATE users SET token='' WHERE token=?",(f.get("token",""),)); c.commit(); return ok({})

@app.get("/typechoUsers/userStatus")
def user_status(token: str=""): return ok({"uid":get_uid(token)})

@app.get("/typechoUsers/regConfig")
def reg_config(): return ok({"openRegister":1,"needInvite":0})

@app.post("/typechoUsers/follow")
async def follow(req: Request):
    f=await form(req); uid=get_uid(f.get("token",""))
    if not uid: return fail("请先登录")
    fid=int(f.get("fanId",0)); c=db()
    if c.execute("SELECT 1 FROM follows WHERE uid=? AND fanId=?",(uid,fid)).fetchone():
        c.execute("DELETE FROM follows WHERE uid=? AND fanId=?",(uid,fid))
    else:
        c.execute("INSERT INTO follows(uid,fanId,created) VALUES(?,?,?)",(uid,fid,int(time.time())))
    c.commit(); return ok({})

@app.get("/typechoUsers/isFollow")
def is_follow(fanId: int=0, token: str=""):
    uid=get_uid(token); r=db().execute("SELECT 1 FROM follows WHERE uid=? AND fanId=?",(uid,fanId)).fetchone() if uid else None
    return ok({"isFollow":1 if r else 0})

@app.get("/typechoUsers/followList")
def follow_list(uid: int=0, page: int=1, limit: int=20):
    off=(page-1)*limit
    return ok([dict(r) for r in db().execute("SELECT u.uid,u.name,u.avatar FROM follows f JOIN users u ON f.fanId=u.uid WHERE f.uid=? LIMIT ? OFFSET ?",(uid,limit,off)).fetchall()])

@app.get("/typechoUsers/fanList")
def fan_list(uid: int=0, page: int=1, limit: int=20):
    off=(page-1)*limit
    return ok([dict(r) for r in db().execute("SELECT u.uid,u.name,u.avatar FROM follows f JOIN users u ON f.uid=u.uid WHERE f.fanId=? LIMIT ? OFFSET ?",(uid,limit,off)).fetchall()])

@app.get("/typechoUsers/getKaptcha")
def kaptcha(): return ok({"img":"","key":""})

# ===== 文章 =====
@app.get("/typechoContents/contentsList")
def contents_list(searchParams: str="{}", limit: int=10, page: int=1, order: str="created DESC", token: str="", type: str="post"):
    uid=get_uid(token); off=(page-1)*limit
    sp=json.loads(searchParams) if searchParams else {}
    rows=db().execute("SELECT * FROM contents WHERE status='publish' ORDER BY isTop DESC,cid DESC LIMIT ? OFFSET ?",(limit,off)).fetchall()
    return ok([build_content(r,uid) for r in rows])

@app.get("/typechoContents/contentsInfo")
def contents_info(cid: int=0, token: str=""):
    uid=get_uid(token); c=db()
    row=c.execute("SELECT * FROM contents WHERE cid=? AND status='publish'",(cid,)).fetchone()
    if not row: return fail("文章不存在")
    c.execute("UPDATE contents SET views=views+1 WHERE cid=?",(cid,)); c.commit()
    return ok(build_content(row,uid))

@app.post("/typechoContents/contentsAdd")
async def contents_add(req: Request):
    f=await form(req); uid=get_uid(f.get("token",""))
    if not uid: return fail("请先登录")
    c=db(); c.execute("INSERT INTO contents(title,text,created,modified,authorId) VALUES(?,?,?,?,?)",
        (f.get("title",""),f.get("text",""),int(time.time()),int(time.time()),uid)); c.commit()
    return ok({"cid":c.execute("SELECT last_insert_rowid() id").fetchone()["id"]})

@app.post("/typechoContents/contentsUpdate")
async def contents_update(req: Request):
    f=await form(req); uid=get_uid(f.get("token",""))
    c=db(); c.execute("UPDATE contents SET title=?,text=?,modified=? WHERE cid=? AND authorId=?",
        (f.get("title",""),f.get("text",""),int(time.time()),f.get("cid",0),uid)); c.commit(); return ok({})

@app.post("/typechoContents/contentsDelete")
async def contents_delete(req: Request):
    f=await form(req); c=db(); c.execute("DELETE FROM contents WHERE cid=?",(f.get("cid",0),)); c.commit(); return ok({})

@app.get("/typechoContents/followContents")
def follow_contents(page: int=1, limit: int=10, token: str=""):
    uid=get_uid(token); off=(page-1)*limit
    rows=db().execute("SELECT c.* FROM contents c JOIN follows f ON c.authorId=f.fanId WHERE f.uid=? AND c.status='publish' ORDER BY c.cid DESC LIMIT ? OFFSET ?",(uid,limit,off)).fetchall()
    return ok([build_content(r,uid) for r in rows])

@app.get("/typechoContents/allData")
def all_data():
    return ok({"articleNum":db().execute("SELECT COUNT(*) c FROM contents").fetchone()["c"],
               "commentNum":db().execute("SELECT COUNT(*) c FROM comments").fetchone()["c"],
               "userNum":db().execute("SELECT COUNT(*) c FROM users").fetchone()["c"]})

# ===== 评论 =====
@app.get("/typechoComments/commentsList")
def comments_list(cid: int=0, page: int=1, limit: int=20):
    off=(page-1)*limit
    return ok([dict(r) for r in db().execute("SELECT * FROM comments WHERE cid=? AND status=1 ORDER BY coid DESC LIMIT ? OFFSET ?",(cid,limit,off)).fetchall()])

@app.post("/typechoComments/commentsAdd")
async def comments_add(req: Request):
    f=await form(req); uid=get_uid(f.get("token",""))
    cid=int(f.get("cid",0)); c=db(); u=get_user(uid)
    c.execute("INSERT INTO comments(cid,authorId,text,created,authorName) VALUES(?,?,?,?,?)",(cid,uid,f.get("text",""),int(time.time()),u["name"] if u else "匿名"))
    c.execute("UPDATE contents SET commentsNum=commentsNum+1 WHERE cid=?",(cid,)); c.commit()
    return ok({})

# ===== 分类 =====
@app.get("/typechoMetas/metasList")
def metas_list():
    return ok([dict(r) for r in db().execute("SELECT * FROM metas WHERE type='category' ORDER BY orderNum").fetchall()])

@app.get("/typechoMetas/metaInfo")
def meta_info(mid: int=0):
    r=db().execute("SELECT * FROM metas WHERE mid=?",(mid,)).fetchone(); return ok(dict(r) if r else {})

@app.get("/typechoMetas/selectContents")
def select_contents(mid: int=0, page: int=1, limit: int=10, token: str=""):
    uid=get_uid(token); off=(page-1)*limit
    rows=db().execute("SELECT c.* FROM contents c JOIN relationships r ON c.cid=r.cid WHERE r.mid=? AND c.status='publish' ORDER BY c.cid DESC LIMIT ? OFFSET ?",(mid,limit,off)).fetchall()
    return ok([build_content(r,uid) for r in rows])

# ===== 首页 =====
@app.get("/typechoHome/bannerList")
def banner_list():
    return ok([dict(r) for r in db().execute("SELECT aid as cid,title,image as url FROM ads WHERE type='banner' AND status=1 ORDER BY sort").fetchall()])

@app.get("/typechoHome/featureList")
def feature_list(): return ok([])
@app.get("/typechoHome/routeList")
def route_list(): return ok([])

# ===== 点赞收藏 =====
@app.post("/typechoUserlog/addLog")
async def add_log(req: Request):
    f=await form(req); uid=get_uid(f.get("token",""))
    if not uid: return fail("请先登录")
    cid=int(f.get("cid",0)); typ=f.get("type","like"); c=db()
    try:
        c.execute("INSERT INTO likes(uid,cid,type,created) VALUES(?,?,?,?)",(uid,cid,typ,int(time.time())))
        if typ=="like": c.execute("UPDATE contents SET likes=likes+1 WHERE cid=?",(cid,))
        c.commit()
    except: pass
    return ok({})

@app.get("/typechoUserlog/isMark")
def is_mark(cid: int=0, token: str="", type: str="like"):
    uid=get_uid(token)
    if not uid: return ok({"is":0})
    r=db().execute("SELECT 1 FROM likes WHERE uid=? AND cid=? AND type=?",(uid,cid,type)).fetchone()
    return ok({"is":1 if r else 0})

@app.get("/typechoUserlog/markList")
def mark_list(page: int=1, limit: int=10, type: str="mark", token: str=""):
    uid=get_uid(token); off=(page-1)*limit
    rows=db().execute("SELECT c.* FROM likes l JOIN contents c ON l.cid=c.cid WHERE l.uid=? AND l.type=? ORDER BY l.created DESC LIMIT ? OFFSET ?",(uid,type,limit,off)).fetchall()
    return ok([build_content(r,uid) for r in rows])

@app.post("/typechoUserlog/removeLog")
async def remove_log(req: Request):
    f=await form(req); uid=get_uid(f.get("token","")); c=db()
    c.execute("DELETE FROM likes WHERE uid=? AND cid=?",(uid,int(f.get("cid",0)))); c.commit(); return ok({})

# ===== 签到 =====
@app.get("/typechoSign/signCenter")
def sign_center(token: str=""):
    uid=get_uid(token); today=int(time.time()//86400)
    signed=db().execute("SELECT 1 FROM signs WHERE uid=? AND created=?",(uid,today)).fetchone()
    return ok({"isSign":1 if signed else 0,"days":db().execute("SELECT COUNT(*) c FROM signs WHERE uid=?",(uid,)).fetchone()["c"]})

@app.post("/typechoSign/doSign")
async def do_sign(req: Request):
    f=await form(req); uid=get_uid(f.get("token",""))
    if not uid: return fail("请先登录")
    today=int(time.time()//86400); c=db()
    if c.execute("SELECT 1 FROM signs WHERE uid=? AND created=?",(uid,today)).fetchone(): return fail("今日已签到")
    c.execute("INSERT INTO signs(uid,created,reward) VALUES(?,?,?)",(uid,today,10))
    c.execute("UPDATE users SET coins=coins+10 WHERE uid=?",(uid,))
    c.commit(); return ok({"reward":10})

# ===== 商城 =====
@app.get("/typechoShop/shopList")
def shop_list(page: int=1, limit: int=20, typeId: int=0):
    off=(page-1)*limit
    return ok([dict(r) for r in db().execute("SELECT * FROM shops WHERE status=1 ORDER BY sid DESC LIMIT ? OFFSET ?",(limit,off)).fetchall()])

@app.get("/typechoShop/shopInfo")
def shop_info(sid: int=0):
    r=db().execute("SELECT * FROM shops WHERE sid=?",(sid,)).fetchone(); return ok(dict(r) if r else {})

@app.get("/typechoShop/shopTypeList")
def shop_type_list():
    return ok([dict(r) for r in db().execute("SELECT * FROM shop_types").fetchall()])

@app.post("/typechoShop/buyShop")
async def buy_shop(req: Request):
    f=await form(req); uid=get_uid(f.get("token",""))
    if not uid: return fail("请先登录")
    sid=int(f.get("sid",0)); c=db(); shop=c.execute("SELECT * FROM shops WHERE sid=?",(sid,)).fetchone()
    if not shop: return fail("商品不存在")
    u=get_user(uid)
    if u["coins"]<shop["price"]: return fail("金币不足")
    c.execute("UPDATE users SET coins=coins-? WHERE uid=?",(shop["price"],uid))
    c.execute("INSERT INTO orders(uid,sid,price,status,created) VALUES(?,?,?,?,?)",(uid,sid,shop["price"],1,int(time.time())))
    c.commit(); return ok({})

# ===== 聊天/消息 =====
@app.get("/typechoChat/myChat")
def my_chat(token: str=""):
    uid=get_uid(token)
    return ok([dict(r) for r in db().execute("SELECT * FROM chats ORDER BY cgid DESC").fetchall()])

@app.get("/typechoChat/msgList")
def msg_list(cgid: int=0, page: int=1, limit: int=50):
    off=(page-1)*limit
    return ok([dict(r) for r in db().execute("SELECT * FROM chat_msgs WHERE cgid=? ORDER BY mid DESC LIMIT ? OFFSET ?",(cgid,limit,off)).fetchall()])

@app.post("/typechoChat/sendMsg")
async def send_msg(req: Request):
    f=await form(req); uid=get_uid(f.get("token",""))
    c=db(); c.execute("INSERT INTO chat_msgs(cgid,senderId,text,created) VALUES(?,?,?,?)",(int(f.get("cgid",0)),uid,f.get("text",""),int(time.time()))); c.commit(); return ok({})

@app.get("/typechoUsers/inbox")
def inbox(token: str="", page: int=1, limit: int=20):
    uid=get_uid(token); off=(page-1)*limit
    return ok([dict(r) for r in db().execute("SELECT * FROM inbox WHERE uid=? ORDER BY id DESC LIMIT ? OFFSET ?",(uid,limit,off)).fetchall()])

@app.get("/typechoUsers/unreadNum")
def unread_num(token: str=""):
    uid=get_uid(token); return ok({"num":db().execute("SELECT COUNT(*) c FROM inbox WHERE uid=? AND isRead=0",(uid,)).fetchone()["c"]})

# ===== 活动/广告/圈子 =====
@app.get("/typechoActivity/activityList")
def activity_list():
    return ok([dict(r) for r in db().execute("SELECT * FROM activities WHERE status=1").fetchall()])

@app.get("/typechoAds/adsList")
def ads_list():
    return ok([dict(r) for r in db().execute("SELECT * FROM ads WHERE status=1 ORDER BY sort").fetchall()])

@app.get("/typechoSpace/spaceList")
def space_list():
    return ok([dict(r) for r in db().execute("SELECT * FROM spaces ORDER BY spid DESC").fetchall()])

# ===== 上传 =====
@app.post("/upload/full")
async def upload_file(file: UploadFile = File(...)):
    os.makedirs("uploads", exist_ok=True)
    fname=f"{uuid.uuid4().hex}_{file.filename}"
    with open(f"uploads/{fname}","wb") as f: f.write(await file.read())
    return ok({"url":f"/uploads/{fname}"})

@app.get("/uploads/{fname}")
def serve_upload(fname: str):
    return FileResponse(f"uploads/{fname}")

# ===== 系统配置 =====
@app.get("/system/app")
def system_app(key: str=""):
    return ok({"name":"云屿","mail":"admin@yunyu.com","logo":"","website":"","currencyName":"金币",
               "adpid":"","adsVideoType":1,"versionName":"1.5.7","versionCode":52,"registerType":1})

# ===== 兜底 =====
@app.api_route("/{full_path:path}", methods=["GET","POST","PUT","DELETE"])
def fallback(full_path: str):
    return ok({})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT",8000)))
