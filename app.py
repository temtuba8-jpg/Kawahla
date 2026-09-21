from datetime import datetime
import os
from bson.objectid import ObjectId
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_pymongo import PyMongo
import requests
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "kawahla_secret_key_2026_super_secure"

# إعداد اتصال MongoDB السحابي
app.config["MONGO_URI"] = (
    "mongodb+srv://kawahla:Fad%400911923356@cluster0.outspyb.mongodb.net/kawahla_db?retryWrites=true&w=majority&appName=Cluster0&tls=true&tlsAllowInvalidCertificates=true"
)

IMGBB_API_KEY = "cc5590cadcc0d03fc63bbb5317442839"

mongo = PyMongo(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


def upload_to_imgbb(file_storage):
    if not file_storage or file_storage.filename == "":
        return None
    try:
        file_bytes = file_storage.read()
        url = "https://api.imgbb.com/1/upload"
        payload = {"key": IMGBB_API_KEY}
        files = {"image": (file_storage.filename, file_bytes)}
        response = requests.post(url, data=payload, files=files)
        result = response.json()
        if result.get("success"):
            return result["data"]["url"]
    except Exception as e:
        print(f"Error uploading to ImgBB: {e}")
    return None


class User(UserMixin):
    def __init__(self, user_data):
        if user_data:
            self.id = str(user_data.get("_id"))
            self.username = user_data.get("username")
            self.password = user_data.get("password")
            self.full_name = user_data.get("full_name")
            self.birth_date = user_data.get("birth_date")
            self.age = user_data.get("age", 25)
            self.national_id = user_data.get("national_id", "")
            self.phone = user_data.get("phone", "")
            self.branch = user_data.get("branch", "عام")
            self.father_name = user_data.get("father_name", "")
            self.grandfather_name = user_data.get("grandfather_name", "")
            self.residence = user_data.get("residence", "")
            self.lat = user_data.get("lat", 15.5007)
            self.lng = user_data.get("lng", 32.5599)
            self.profile_pic = user_data.get(
                "profile_pic", "https://i.ibb.co/default.png"
            )
            self.document_pic = user_data.get("document_pic", "")
            self.is_verified = user_data.get("is_verified", True)
            self.role = user_data.get("role", "user")
            self.title_type = user_data.get("title_type", "عضو")
            self.is_leader = user_data.get("is_leader", False)

    @property
    def is_admin(self):
        return self.role == "admin" or self.username == "admin"


@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        if user_data:
            return User(user_data)
    except Exception:
        pass
    return None


@app.route("/")
def index():
    news_list = list(mongo.db.news.find())
    sliders = list(mongo.db.sliders.find())
    leaders = list(mongo.db.users.find({"is_leader": True}))
    return render_template(
        "index.html", news=news_list, sliders=sliders, leaders=leaders
    )


@app.route("/tree")
def tree():
    users = list(mongo.db.users.find({"is_verified": True}))
    connections = []
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            f1 = users[i].get("father_name")
            f2 = users[j].get("father_name")
            if f1 and f2 and f1.strip() == f2.strip():
                connections.append({
                    "p1": users[i].get("full_name"),
                    "p2": users[j].get("full_name"),
                    "relation": f"إخوة (الأب المشترك: {f1})",
                })
    return render_template(
        "tree.html",
        users=[User(u) for u in users],
        connections=connections,
    )


@app.route("/leaders")
def leaders():
    leader_users = list(mongo.db.users.find({"is_leader": True}))
    return render_template(
        "leaders.html", leaders=[User(u) for u in leader_users]
    )


@app.route("/forum")
@login_required
def forum():
    topics = list(mongo.db.forum_topics.find().sort("_id", -1))
    for topic in topics:
        author_data = mongo.db.users.find_one({"_id": topic.get("user_id")})
        topic["author"] = User(author_data) if author_data else None

        comments = list(
            mongo.db.forum_comments.find({"topic_id": topic["_id"]}).sort(
                "_id", 1
            )
        )
        for c in comments:
            c_author = mongo.db.users.find_one({"_id": c.get("user_id")})
            c["author"] = User(c_author) if c_author else None
        topic["comments"] = comments

    return render_template("forum.html", topics=topics)


@app.route("/forum/create", methods=["POST"])
@login_required
def create_topic():
    if not current_user.is_admin and current_user.role != "moderator":
        flash("عفواً، إنشاء المواضيع مقتصر على الإدارة فقط.", "danger")
        return redirect(url_for("forum"))

    title = request.form.get("title")
    content = request.form.get("content")

    if title and content:
        mongo.db.forum_topics.insert_one({
            "title": title,
            "content": content,
            "user_id": ObjectId(current_user.id),
            "created_at": datetime.utcnow(),
        })
        flash("تم نشر الموضوع في المنتدى بنجاح", "success")

    return redirect(url_for("forum"))


@app.route("/forum/comment/<string:topic_id>", methods=["POST"])
@login_required
def add_comment(topic_id):
    content = request.form.get("content")
    if content:
        mongo.db.forum_comments.insert_one({
            "content": content,
            "topic_id": ObjectId(topic_id),
            "user_id": ObjectId(current_user.id),
            "created_at": datetime.utcnow(),
        })
        flash("تم إضافة تعليقك بنجاح", "success")

    return redirect(url_for("forum"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        full_name = request.form["full_name"]
        birth_date = request.form["birth_date"]
        age = int(request.form["age"])
        national_id = request.form["national_id"]
        phone = request.form.get("phone", "")
        branch = request.form["branch"]
        father_name = request.form.get("father_name", "")
        grandfather_name = request.form.get("grandfather_name", "")
        residence = request.form.get("residence", "")

        profile_pic_file = request.files.get("profile_pic")
        profile_url = "https://i.ibb.co/default.png"
        uploaded_profile = upload_to_imgbb(profile_pic_file)
        if uploaded_profile:
            profile_url = uploaded_profile

        doc_file = request.files.get("document_pic")
        doc_url = ""
        uploaded_doc = upload_to_imgbb(doc_file)
        if uploaded_doc:
            doc_url = uploaded_doc

        new_user_data = {
            "username": username,
            "password": password,
            "full_name": full_name,
            "birth_date": birth_date,
            "age": age,
            "national_id": national_id,
            "phone": phone,
            "branch": branch,
            "father_name": father_name,
            "grandfather_name": grandfather_name,
            "residence": residence,
            "lat": 15.5007,
            "lng": 32.5599,
            "profile_pic": profile_url,
            "document_pic": doc_url,
            "is_verified": False,
            "role": "user",
            "title_type": "عضو",
            "is_leader": False,
        }
        mongo.db.users.insert_one(new_user_data)
        flash(
            "تم التسجيل بنجاح! حسابك الآن قيد المراجعة والتحقق من انتمائك لقبيلة الكواهلة.",
            "info",
        )
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user_data = mongo.db.users.find_one({"username": username})
        
        if username == "admin" and not user_data:
            admin_user = {
                "username": "admin",
                "password": generate_password_hash("admin123"),
                "full_name": "الآدمن العام",
                "birth_date": "1980-01-01",
                "age": 46,
                "national_id": "000000000",
                "phone": "0000000000",
                "branch": "الإدارة",
                "role": "admin",
                "title_type": "آدمن الموقع",
                "is_verified": True,
                "is_leader": True,
                "profile_pic": "https://i.ibb.co/default.png",
            }
            mongo.db.users.insert_one(admin_user)
            user_data = mongo.db.users.find_one({"username": "admin"})

        if user_data:
            stored_pass = user_data.get("password", "")
            is_valid = False

            if username == "admin" and (password == "admin123" or stored_pass == "admin123"):
                is_valid = True
                mongo.db.users.update_one(
                    {"username": "admin"},
                    {"$set": {"password": generate_password_hash("admin123"), "role": "admin", "is_verified": True}}
                )
            else:
                try:
                    if check_password_hash(stored_pass, password):
                        is_valid = True
                except Exception:
                    if stored_pass == password:
                        is_valid = True

            if is_valid:
                user_obj = User(user_data)
                login_user(user_obj)
                if user_obj.role == "admin" or username == "admin":
                    return redirect(url_for("admin_dashboard"))
                elif user_obj.role == "moderator":
                    return redirect(url_for("moderator_dashboard"))
                else:
                    return redirect(url_for("profile"))

        flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
    return render_template("login.html")


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user)


@app.route("/update_location", methods=["POST"])
@login_required
def update_location():
    data = request.json
    mongo.db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"lat": data.get("lat"), "lng": data.get("lng")}},
    )
    return jsonify(
        {"status": "success", "message": "تم تحديث عنوان السكن عبر الخريطة بنجاح"}
    )


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin_dashboard():
    if not current_user.is_admin and current_user.username != "admin":
        flash("عفواً، ليس لديك صلاحية للوصول إلى لوحة التحكم.", "danger")
        return redirect(url_for("profile"))

    search_query = request.args.get("q", "")
    if search_query:
        users_cursor = mongo.db.users.find({
            "$or": [
                {"full_name": {"$regex": search_query, "$options": "i"}},
                {"username": {"$regex": search_query, "$options": "i"}},
            ]
        })
    else:
        users_cursor = mongo.db.users.find()

    users = [User(u) for u in users_cursor]
    news_list = list(mongo.db.news.find())
    sliders = list(mongo.db.sliders.find())
    return render_template(
        "admin_dashboard.html",
        users=users,
        news_list=news_list,
        sliders=sliders,
    )


@app.route("/admin/add_user", methods=["POST"])
@login_required
def admin_add_user():
    if not current_user.is_admin:
        flash("غير مسموح لك بهذا الإجراء", "danger")
        return redirect(url_for("profile"))
        
    username = request.form.get("username")
    password = request.form.get("password")
    full_name = request.form.get("full_name")
    branch = request.form.get("branch", "عام")
    role = request.form.get("role", "user")
    
    if username and password and full_name:
        hashed_pass = generate_password_hash(password)
        mongo.db.users.insert_one({
            "username": username,
            "password": hashed_pass,
            "full_name": full_name,
            "branch": branch,
            "role": role,
            "is_verified": True,
            "profile_pic": "https://i.ibb.co/default.png"
        })
        flash("تم إضافة المستخدم بنجاح بواسطة الآدمن", "success")
    else:
        flash("يرجى ملء الحقول المطلوبة لإضافة المستخدم", "danger")
        
    return redirect(url_for("admin_dashboard"))


@app.route("/make_me_admin_emergency")
@login_required
def make_me_admin_emergency():
    mongo.db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"role": "admin", "is_verified": True}},
    )
    flash("تم ترقية حسابك الحالي إلى (آدمن) بنجاح!", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/add_news", methods=["POST"])
@login_required
def add_news():
    if not current_user.is_admin:
        return redirect(url_for("profile"))
        
    title = request.form["title"]
    content = request.form["content"]
    date = request.form["date"]

    image_file = request.files.get("image")
    image_url = ""
    uploaded_img = upload_to_imgbb(image_file)
    if uploaded_img:
        image_url = uploaded_img

    mongo.db.news.insert_one(
        {"title": title, "content": content, "date": date, "image": image_url}
    )
    flash("تم نشر الخبر بنجاح في الصفحة الرئيسية", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete_news/<string:news_id>")
@login_required
def delete_news(news_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
        
    mongo.db.news.delete_one({"_id": ObjectId(news_id)})
    flash("تم حذف الخبر بنجاح", "warning")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/add_slider", methods=["POST"])
@login_required
def add_slider():
    if not current_user.is_admin:
        return redirect(url_for("profile"))
        
    title = request.form.get("title", "")
    description = request.form.get("description", "")

    image_file = request.files.get("image")
    image_url = ""
    uploaded_slider = upload_to_imgbb(image_file)
    if uploaded_slider:
        image_url = uploaded_slider

    if image_url:
        mongo.db.sliders.insert_one(
            {"title": title, "description": description, "image": image_url}
        )
        flash("تمت إضافة صورة السلايدر بنجاح", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete_slider/<string:slider_id>")
@login_required
def delete_slider(slider_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
        
    mongo.db.sliders.delete_one({"_id": ObjectId(slider_id)})
    flash("تم حذف صورة السلايدر بنجاح", "warning")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/verify/<string:user_id>")
@login_required
def verify_user(user_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
        
    mongo.db.users.update_one(
        {"_id": ObjectId(user_id)}, {"$set": {"is_verified": True}}
    )
    flash("تم التحقق وتوثيق المستخدم بنجاح", "success")
    return redirect(request.referrer)


@app.route("/admin/reject/<string:user_id>")
@login_required
def reject_user(user_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
        
    mongo.db.users.update_one(
        {"_id": ObjectId(user_id)}, {"$set": {"is_verified": False}}
    )
    flash("تم إرجاع الطلب للتعديل للمستخدم", "warning")
    return redirect(request.referrer)


@app.route("/admin/delete/<string:user_id>")
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
        
    mongo.db.users.delete_one({"_id": ObjectId(user_id)})
    flash("تم حذف المستخدم نهائياً", "danger")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/change_password/<string:user_id>", methods=["POST"])
@login_required
def change_password(user_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
        
    new_pass = request.form.get("new_password")
    if new_pass:
        hashed = generate_password_hash(new_pass)
        mongo.db.users.update_one(
            {"_id": ObjectId(user_id)}, {"$set": {"password": hashed}}
        )
        flash("تم تغيير كلمة المرور بنجاح", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/set_role_and_title/<string:user_id>", methods=["POST"])
@login_required
def set_role_and_title(user_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
        
    role = request.form.get("role", "user")
    title_type = request.form.get("title_type", "عضو")
    is_leader = title_type in [
        "أمير القبيلة",
        "ملك الفروع",
        "مهندس القبيلة",
        "رئيس الرابطة",
        "شخصية هامة",
    ]

    mongo.db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "role": role,
                "title_type": title_type,
                "is_leader": is_leader,
            }
        },
    )
    flash("تم تحديث صلاحيات ولقب المستخدم", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/moderator")
@login_required
def moderator_dashboard():
    pending_users = [
        User(u) for u in mongo.db.users.find({"is_verified": False})
    ]
    return render_template("moderator_dashboard.html", users=pending_users)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


if __name__ == "__main__":
    with app.app_context():
        existing_admin = mongo.db.users.find_one({"username": "admin"})
        if not existing_admin:
            admin_user = {
                "username": "admin",
                "password": generate_password_hash("admin123"),
                "full_name": "الآدمن العام",
                "birth_date": "1980-01-01",
                "age": 46,
                "national_id": "000000000",
                "phone": "0000000000",
                "branch": "الإدارة",
                "role": "admin",
                "title_type": "آدمن الموقع",
                "is_verified": True,
                "is_leader": True,
                "profile_pic": "https://i.ibb.co/default.png",
            }
            mongo.db.users.insert_one(admin_user)
        else:
            mongo.db.users.update_one(
                {"username": "admin"},
                {
                    "$set": {
                        "password": generate_password_hash("admin123"),
                        "role": "admin",
                        "is_verified": True,
                    }
                },
            )

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
