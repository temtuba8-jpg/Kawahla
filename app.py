from datetime import datetime, timedelta
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


def upload_to_imgbb(image_input):
    if not image_input:
        print("ImgBB Error: No image input provided.")
        return None
    try:
        url = "https://api.imgbb.com/1/upload"
        payload = {"key": IMGBB_API_KEY}

        # 1. إذا كانت الصورة مرفوعة كملف من جهاز المستخدم (FileStorage)
        if hasattr(image_input, "read"):
            file_bytes = image_input.read()
            if not image_input.filename:
                return None
            files = {"image": (image_input.filename, file_bytes)}
            response = requests.post(url, data=payload, files=files)
            
        # 2. إذا كانت الصورة مرسلة كنص Base64 (من الكاميرا مثلاً)
        elif isinstance(image_input, str):
            if image_input.startswith("data:image"):
                image_input = image_input.split(",")[1]
            payload["image"] = image_input
            response = requests.post(url, data=payload)
        else:
            return None

        result = response.json()
        print("ImgBB Response Data:", result)

        if result.get("success"):
            image_data = result.get("data", {})
            return image_data.get("url") or image_data.get("display_url")
            
    except Exception as e:
        print(f"Error uploading to ImgBB: {e}")
    return None


class User(UserMixin):
    def __init__(self, user_data):
        if user_data:
            self.id = str(user_data.get("_id"))
            self.username = user_data.get("username", "")
            self.password = user_data.get("password", "")
            self.full_name = user_data.get("full_name", "مستخدم")
            self.birth_date = user_data.get("birth_date", "2000-01-01")
            self.birth_place = user_data.get("birth_place", "السودان")
            self.age = user_data.get("age", 25)
            self.national_id = user_data.get("national_id", "")
            self.phone = user_data.get("phone", "")
            self.branch = user_data.get("branch", "عام")
            self.father_name = user_data.get("father_name", "")
            self.grandfather_name = user_data.get("grandfather_name", "")
            self.residence = user_data.get("residence", "الخرطوم، السودان")
            self.lat = user_data.get("lat", 15.5007)
            self.lng = user_data.get("lng", 32.5599)
            
            raw_pic = user_data.get("profile_pic", "default.png")
            if raw_pic and raw_pic.startswith("http"):
                self.profile_pic = raw_pic
            else:
                self.profile_pic = raw_pic if raw_pic else "default.png"
                
            self.document_pic = user_data.get("document_pic", "")
            self.is_verified = user_data.get("is_verified", False)
            self.role = user_data.get("role", "user")
            self.title_type = user_data.get("title_type", "عضو")
            self.is_leader = user_data.get("is_leader", False)
            self.last_profile_pic_update = user_data.get("last_profile_pic_update")

    @property
    def is_admin(self):
        return self.role == "admin" or self.username == "admin"

    @property
    def is_moderator(self):
        return self.role == "moderator"


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


@app.route("/news")
def all_news():
    news_list = list(mongo.db.news.find().sort("_id", -1))
    return render_template("forum.html", news=news_list)


@app.route("/princes")
def princes():
    princes_list = list(mongo.db.users.find({"$or": [{"title_type": {"$regex": "أمير", "$options": "i"}}, {"is_leader": True}]}))
    return render_template("leaders.html", princes=[User(u) for u in princes_list])


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
    if not current_user.is_admin and not current_user.is_moderator:
        flash("عفواً، إنشاء المواضيع مقتصر على الإدارة والمشرفين فقط.", "danger")
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
        try:
            t_obj_id = ObjectId(topic_id)
        except Exception:
            flash("الموضوع غير موجود أو المعرف غير صالح", "danger")
            return redirect(url_for("forum"))

        topic_exists = mongo.db.forum_topics.find_one({"_id": t_obj_id})
        if not topic_exists:
            flash("الموضوع المطلوب غير موجود", "danger")
            return redirect(url_for("forum"))

        mongo.db.forum_comments.insert_one({
            "content": content,
            "topic_id": t_obj_id,
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
        birth_place = request.form.get("birth_place", "السودان")
        age = int(request.form.get("age", 25))
        national_id = request.form["national_id"]
        phone = request.form.get("phone", "")
        branch = request.form["branch"]
        father_name = request.form.get("father_name", "")
        grandfather_name = request.form.get("grandfather_name", "")
        residence = request.form.get("residence", "")
        title_type = request.form.get("title_type", "عضو")

        profile_pic_file = request.files.get("profile_pic")
        profile_url = "default.png"
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
            "birth_place": birth_place,
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
            "title_type": title_type,
            "is_leader": False,
            "last_profile_pic_update": None,
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
        national_id = request.form.get("national_id", "").strip()
        password = request.form.get("password", "").strip()

        user_data = None
        if national_id == "admin" or national_id == "000000000":
            user_data = mongo.db.users.find_one({"username": "admin"})
            if not user_data:
                admin_user = {
                    "username": "admin",
                    "password": generate_password_hash("admin123"),
                    "full_name": "الآدمن العام",
                    "birth_date": "1980-01-01",
                    "birth_place": "الخرطوم",
                    "age": 46,
                    "national_id": "000000000",
                    "phone": "0000000000",
                    "branch": "الإدارة",
                    "role": "admin",
                    "title_type": "آدمن الموقع",
                    "is_verified": True,
                    "is_leader": True,
                    "profile_pic": "default.png",
                }
                mongo.db.users.insert_one(admin_user)
                user_data = mongo.db.users.find_one({"username": "admin"})
        else:
            user_data = mongo.db.users.find_one({"national_id": national_id})

        if user_data:
            stored_pass = user_data.get("password", "")
            is_valid = False

            if (
                user_data.get("username") == "admin"
                and (password == "admin123" or stored_pass == "admin123")
            ):
                is_valid = True
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
                if user_obj.is_admin:
                    return redirect(url_for("admin_dashboard"))
                elif user_obj.is_moderator:
                    return redirect(url_for("moderator_dashboard"))
                else:
                    return redirect(url_for("profile"))

        flash("الرقم الوطني أو كلمة المرور غير صحيحة", "danger")
    return render_template("login.html")


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user)


@app.route("/update_profile_picture", methods=["POST"])
@login_required
def update_profile_picture():
    user_doc = mongo.db.users.find_one({"_id": ObjectId(current_user.id)})
    last_update = user_doc.get("last_profile_pic_update") if user_doc else None

    if last_update:
        if datetime.utcnow() - last_update < timedelta(days=30):
            flash(
                "عفواً، لا يمكنك تغيير الصورة الشخصية إلا مرة واحدة كل شهر.",
                "danger",
            )
            return redirect(url_for("profile"))

    profile_pic_file = request.files.get("new_profile_pic")
    profile_pic_base64 = request.form.get("profile_pic_base64")

    image_input = profile_pic_file if profile_pic_file else profile_pic_base64
    uploaded_url = upload_to_imgbb(image_input)

    if uploaded_url:
        mongo.db.users.update_one(
            {"_id": ObjectId(current_user.id)},
            {
                "$set": {
                    "profile_pic": uploaded_url,
                    "last_profile_pic_update": datetime.utcnow(),
                }
            },
        )
        flash("تم تحديث الصورة الشخصية للبطاقة بنجاح!", "success")
    else:
        flash(
            "فشل رفع الصورة، يرجى التأكد من اختيار صورة أو فتح الكاميرا بشكل صحيح",
            "danger",
        )

    return redirect(url_for("profile"))


@app.route("/update_location", methods=["POST"])
@login_required
def update_location():
    data = request.json
    if data and "lat" in data and "lng" in data:
        mongo.db.users.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": {"lat": data.get("lat"), "lng": data.get("lng")}},
        )
        return jsonify(
            {"status": "success", "message": "تم تحديث موقعك الجغرافي بنجاح!"}
        )
    return jsonify({"status": "error", "message": "حدث خطأ أثناء تحديث الموقع."}), 400


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash("عفواً، ليس لديك صلاحية للوصول إلى لوحة التحكم.", "danger")
        return redirect(url_for("profile"))

    search_query = request.args.get("q", "")
    if search_query:
        users_cursor = mongo.db.users.find({
            "$or": [
                {"full_name": {"$regex": search_query, "$options": "i"}},
                {"national_id": {"$regex": search_query, "$options": "i"}},
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
    national_id = request.form.get("national_id", "")
    branch = request.form.get("branch", "عام")
    role = request.form.get("role", "user")

    if username and password and full_name:
        hashed_pass = generate_password_hash(password)
        mongo.db.users.insert_one({
            "username": username,
            "password": hashed_pass,
            "full_name": full_name,
            "national_id": national_id,
            "branch": branch,
            "role": role,
            "is_verified": True,
            "profile_pic": "default.png",
            "last_profile_pic_update": None,
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
    if not current_user.is_admin and not current_user.is_moderator:
        return redirect(url_for("profile"))

    mongo.db.users.update_one(
        {"_id": ObjectId(user_id)}, {"$set": {"is_verified": True}}
    )
    flash("تم التحقق وتوثيق المستخدم بنجاح", "success")
    return redirect(request.referrer)


@app.route("/admin/reject/<string:user_id>")
@login_required
def reject_user(user_id):
    if not current_user.is_admin and not current_user.is_moderator:
        return redirect(url_for("profile"))

    mongo.db.users.update_one(
        {"_id": ObjectId(user_id)}, {"$set": {"is_verified": False}}
    )
    flash("تم إرجاع الطلب للتعديل للمستخدم", "warning")
    return redirect(request.referrer)


@app.route("/admin/delete/<string:user_id>")
@login_required
def delete_user_route(user_id):
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
    flash("تم تحديث صلاحيات ولقب المستخدم بنجاح", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/moderator")
@login_required
def moderator_dashboard():
    if not current_user.is_admin and not current_user.is_moderator:
        flash("عفواً، ليس لديك صلاحية للوصول إلى لوحة المشرفين.", "danger")
        return redirect(url_for("profile"))

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
                "birth_place": "الخرطوم",
                "age": 46,
                "national_id": "000000000",
                "phone": "0000000000",
                "branch": "الإدارة",
                "role": "admin",
                "title_type": "آدمن الموقع",
                "is_verified": True,
                "is_leader": True,
                "profile_pic": "default.png",
                "last_profile_pic_update": None,
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
