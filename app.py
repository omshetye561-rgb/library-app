from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask import request, redirect, url_for, flash, render_template
from datetime import datetime
import requests

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    author = db.Column(db.String(100))
    stock = db.Column(db.Integer, default=1)

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    total_due = db.Column(db.Float, default=0.0)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'))
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'))
    issue_date = db.Column(db.DateTime)
    return_date = db.Column(db.DateTime)
    fee = db.Column(db.Float, default=0.0)

    book = db.relationship('Book', backref='transactions')
    member = db.relationship('Member', backref='transactions')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/books')
def books():
    all_books = Book.query.all()
    return render_template('books.html', books=all_books)

@app.route('/members')
def members():
    all_members = Member.query.all()
    return render_template('members.html', members=all_members)

@app.route('/transactions')
def transactions():
    all_txns = Transaction.query.all()
    return render_template('transactions.html', transactions=all_txns)

@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        stock = int(request.form['stock'])
        new_book = Book(title=title, author=author, stock=stock)
        db.session.add(new_book)
        db.session.commit()
        flash("Book added successfully!", "success")
        return redirect(url_for('books'))
    return render_template('add_book.html')

@app.route('/add_member', methods=['GET', 'POST'])
def add_member():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        new_member = Member(name=name, email=email)
        db.session.add(new_member)
        db.session.commit()
        flash("Member added successfully!", "success")
        return redirect(url_for('members'))
    return render_template('add_member.html')

@app.route('/issue', methods=['GET', 'POST'])
def issue_book():
    members = Member.query.all()
    books = Book.query.filter(Book.stock > 0).all()

    if request.method == 'POST':
        book_id = int(request.form['book_id'])
        member_id = int(request.form['member_id'])

        book = Book.query.get(book_id)
        member = Member.query.get(member_id)

        if member.total_due > 500:
            flash("Cannot issue: Member owes more than ₹500!", "danger")
            return redirect(url_for('issue_book'))

        if book.stock < 1:
            flash("Book out of stock!", "danger")
            return redirect(url_for('issue_book'))

        txn = Transaction(book_id=book_id, member_id=member_id, issue_date=datetime.utcnow())
        book.stock -= 1
        db.session.add(txn)
        db.session.commit()
        flash("Book issued!", "success")
        return redirect(url_for('transactions'))

    return render_template('issue_book.html', books=books, members=members)

@app.route('/return/<int:txn_id>', methods=['POST'])
def return_book(txn_id):
    txn = Transaction.query.get_or_404(txn_id)
    if txn.return_date:
        flash("Book already returned!", "info")
        return redirect(url_for('transactions'))

    txn.return_date = datetime.utcnow()
    txn.fee = 100.0  # Fixed fee
    txn.book.stock += 1
    txn.member.total_due += txn.fee
    db.session.commit()
    flash("Book returned and fee charged!", "success")
    return redirect(url_for('transactions'))

@app.route('/search')
def search_books():
    query = request.args.get('q', '').strip()
    if query:
        results = Book.query.filter(
            (Book.title.ilike(f"%{query}%")) | (Book.author.ilike(f"%{query}%"))
        ).all()
    else:
        results = []
    return render_template('search.html', results=results, query=query)

@app.route('/import', methods=['GET', 'POST'])
def import_books():
    if request.method == 'POST':
        count = int(request.form.get('count', 20))
        filters = {
            'title': request.form.get('title', ''),
            'authors': request.form.get('author', ''),
            'publisher': request.form.get('publisher', ''),
            'isbn': request.form.get('isbn', ''),
            'page': request.form.get('page', ''),
        }

        page = 1
        imported = 0

        while imported < count:
            # Build the query string from non-empty filters
            query_string = "&".join([
                f"{key}={value}" for key, value in filters.items() if value.strip()
            ])
            url = f"https://frappe.io/api/method/frappe-library?page={page}&{query_string}"

            r = requests.get(url)
            data = r.json().get('message', [])
            if not data:
                break

            for item in data:
                if imported >= count:
                    break
                new_book = Book(
                    title=item['title'],
                    author=item['authors'],
                    stock=1
                )
                db.session.add(new_book)
                imported += 1
            page += 1

        db.session.commit()
        flash(f"{imported} books imported successfully.", "success")
        return redirect(url_for('books'))

    return render_template('import_books.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

