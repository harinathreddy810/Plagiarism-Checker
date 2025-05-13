from flask import Flask, render_template, request, redirect, url_for, flash
import nltk
from docx import Document
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from PyPDF2 import PdfReader
import re
import mysql.connector
from mysql.connector import Error
from waitress import serve  # Import waitress

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with your own secret key

def setup_nltk():
    """Ensures NLTK resources are set up correctly."""
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')

def read_text_file(file_path):
    """Reads the content of a text file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def read_pdf(file_path):
    """Reads the content of a PDF file."""
    full_text = []
    with open(file_path, 'rb') as file:
        reader = PdfReader(file)
        for page in reader.pages:
            full_text.append(page.extract_text())
    return ' '.join(full_text)

def preprocess_text(text):
    """Preprocesses the text by lowercasing and removing special characters."""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text

def read_document(file_path):
    """Reads the content of a document file and returns it as a single string."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.docx':
        doc = Document(file_path)
        full_text = [para.text for para in doc.paragraphs]
        return ' '.join(full_text)
    elif ext == '.pdf':
        return read_pdf(file_path)
    elif ext == '.txt':
        return read_text_file(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

def calc_cosine_similarity(doc1, doc2):
    """Calculates the cosine similarity between two documents."""
    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform([doc1, doc2])
    return cosine_similarity(vectors[0:1], vectors[1:2])

def find_plagiarism(file1, file2):
    """Finds the plagiarism score between two documents."""
    doc1 = preprocess_text(read_document(file1))
    doc2 = preprocess_text(read_document(file2))
    similarity_score = calc_cosine_similarity(doc1, doc2)[0][0]
    return similarity_score

def store_result_in_db(file1, file2, similarity_score):
    """Stores the plagiarism result in a MySQL database."""
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='1234',
            database='plagiarism_checker'
        )
        if connection.is_connected():
            cursor = connection.cursor()
            create_table_query = """
            CREATE TABLE IF NOT EXISTS plagiarism_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                file1 VARCHAR(255),
                file2 VARCHAR(255),
                similarity_score FLOAT,
                check_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            cursor.execute(create_table_query)
            insert_query = """
            INSERT INTO plagiarism_results (file1, file2, similarity_score)
            VALUES (%s, %s, %s)
            """
            cursor.execute(insert_query, (file1, file2, similarity_score))
            connection.commit()
    
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
    
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file1 = request.files['file1']
        file2 = request.files['file2']
        if file1 and file2:
            file1_path = os.path.join('uploads', file1.filename)
            file2_path = os.path.join('uploads', file2.filename)
            file1.save(file1_path)
            file2.save(file2_path)
            
            similarity_score = find_plagiarism(file1_path, file2_path)
            store_result_in_db(file1.filename, file2.filename, similarity_score)
            flash(f"Similarity Score: {similarity_score * 100:.2f}%", "success")
            return redirect(url_for('index'))
        else:
            flash("Please upload two files.", "error")
    
    return render_template('index.html')

if __name__ == '__main__':
    setup_nltk()
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    # Use Waitress to serve the app
    serve(app, host='0.0.0.0', port=8080)  # Replace 8080 with the desired port if needed
