import os
from flask import Flask, render_template, request, redirect, send_from_directory
import mysql.connector

app = Flask(__name__, template_folder='templates')

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="123456",
        database="reviewer_db",
        charset="utf8"
    )


@app.route('/style.css')
def serve_css():
    return send_from_directory('.', 'style.css')


# Main Dashboard Engine
@app.route('/')
def index():
    category_filter = request.args.get('cat', '')
    search_query = request.args.get('search', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Fetch all dynamic categories for the sidebar menu
    cursor.execute("SELECT * FROM categories ORDER BY name ASC")
    categories = cursor.fetchall()

    # 2. Fetch files based on filters
    if category_filter:
        query = "SELECT * FROM reviewers WHERE category = %s ORDER BY upload_date DESC"
        cursor.execute(query, (category_filter,))
    elif search_query:
        query = "SELECT * FROM reviewers WHERE filename LIKE %s ORDER BY upload_date DESC"
        cursor.execute(query, (f"%{search_query}%",))
    else:
        cursor.execute("SELECT * FROM reviewers ORDER BY upload_date DESC")

    files = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('index.html', files=files, categories=categories, search_query=search_query)


# Route to Create a Category
@app.route('/add-category', methods=['POST'])
def add_category():
    cat_name = request.form.get('category_name', '').strip()
    if cat_name:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO categories (name) VALUES (%s)", (cat_name,))
            conn.commit()
        except mysql.connector.Error as err:
            print(f"Category already exists or DB error: {err}")
        cursor.close()
        conn.close()
    return redirect('/')


# Route to Remove a Category
@app.route('/delete-category/<string:cat_name>')
def delete_category(cat_name):
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Delete the category itself
    cursor.execute("DELETE FROM categories WHERE name = %s", (cat_name,))

    # 2. Re-label any files in that deleted category to 'General' so they aren't lost
    cursor.execute("UPDATE reviewers SET category = 'General' WHERE category = %s", (cat_name,))

    conn.commit()
    cursor.close()
    conn.close()
    return redirect('/')


# Route to Handle File Uploads
@app.route('/upload', methods=['POST'])
def handle_upload():
    if 'file' not in request.files:
        return redirect('/')

    uploaded_file = request.files['file']
    selected_category = request.form.get('category', 'General')

    if uploaded_file.filename != '':
        target_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
        uploaded_file.save(target_path)

        conn = get_db_connection()
        cursor = conn.cursor()
        sql = "INSERT INTO reviewers (filename, category, file_path) VALUES (%s, %s, %s)"
        cursor.execute(sql, (uploaded_file.filename, selected_category, target_path))
        conn.commit()
        cursor.close()
        conn.close()

    return redirect(f"/?cat={selected_category}" if selected_category != 'General' else '/')


# Route to Download/View File
@app.route('/download/<filename>')
def download_reviewer(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# Route to Delete File
@app.route('/delete/<int:file_id>')
def delete_reviewer(file_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT file_path FROM reviewers WHERE id = %s", (file_id,))
    file_record = cursor.fetchone()

    if file_record:
        try:
            if os.path.exists(file_record['file_path']):
                os.remove(file_record['file_path'])
        except Exception as e:
            print(f"File error: {e}")

        cursor.execute("DELETE FROM reviewers WHERE id = %s", (file_id,))
        conn.commit()

    cursor.close()
    conn.close()
    return redirect(request.referrer or '/')


if __name__ == '__main__':
    app.run(debug=True)