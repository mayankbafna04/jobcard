from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobcards.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'  # Required for flash messages
db = SQLAlchemy(app)

# Job Card Model
class JobCard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    job_card_number = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(20), nullable=False)
    parts_used = db.Column(db.String(500), nullable=False)  # Comma-separated parts

    def __repr__(self):
        return f'<JobCard {self.job_card_number}>'

# Part Model (for managing parts and their quantities)
class Part(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity_sent = db.Column(db.Integer, nullable=False)  # Pieces sent by admin
    quantity_available = db.Column(db.Integer, nullable=False)  # Available pieces

    def __repr__(self):
        return f'<Part {self.name}>'

# Database initialization
def create_db():
    with app.app_context():
        db.create_all()

# Call create_db() explicitly when running the app
create_db()

# Route for the Job Card Submission Form (index.html)
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Get data from the form
        date = request.form['date']
        customer_name = request.form['customerName']
        job_card_number = request.form['jobCardNumber']
        description = request.form['description']
        amount = request.form['amount']
        payment_mode = request.form['paymentMode']
        parts_used = ', '.join(request.form.getlist('partsUsed'))  # Join parts into a string

        # Check if job card number already exists in the database
        existing_job_card = JobCard.query.filter_by(job_card_number=job_card_number).first()
        if existing_job_card:
            flash('Job card number already exists! Please enter a unique Job Card Number.', 'error')
            return redirect(url_for('index'))  # Redirect back to the form if job card exists

        # Create a new job card
        new_job_card = JobCard(
            date=date,
            customer_name=customer_name,
            job_card_number=job_card_number,
            description=description,
            amount=amount,
            payment_mode=payment_mode,
            parts_used=parts_used
        )

        # Add the new job card to the database
        db.session.add(new_job_card)
        db.session.commit()

        # Deduct from available stock (pieces) for each part used
        for part_name in parts_used.split(', '):
            part = Part.query.filter_by(name=part_name).first()
            if part:
                if part.quantity_available > 0:
                    part.quantity_available -= 1  # Subtract one piece from available stock
                    db.session.commit()
                    print(f"Deducted 1 {part_name}, new stock: {part.quantity_available}")
                else:
                    flash(f"Not enough stock for {part_name}.", 'warning')
            else:
                flash(f"Part {part_name} not found.", 'error')

        flash('Job Card successfully submitted!', 'success')  # Flash success message
        return redirect(url_for('index'))  # Redirect to index after submission

    return render_template('index.html')


# Route for the Admin Page (admin.html)
@app.route('/admin')
def admin():
    job_cards = JobCard.query.all()  # Get all job cards
    return render_template('admin.html', job_cards=job_cards)

# Route to delete a job card
@app.route('/delete/<int:job_card_id>')
def delete_job_card(job_card_id):
    job_card = JobCard.query.get_or_404(job_card_id)
    db.session.delete(job_card)
    db.session.commit()
    return redirect(url_for('admin'))

# Route to edit a job card (GET & POST)
@app.route('/edit/<int:job_card_id>', methods=['GET', 'POST'])
def edit_job_card(job_card_id):
    job_card = JobCard.query.get_or_404(job_card_id)

    if request.method == 'POST':
        # Update job card with form data
        job_card.date = request.form['date']
        job_card.customer_name = request.form['customerName']
        job_card.job_card_number = request.form['jobCardNumber']
        job_card.description = request.form['description']
        job_card.amount = request.form['amount']
        job_card.payment_mode = request.form['paymentMode']
        job_card.parts_used = ', '.join(request.form.getlist('partsUsed'))

        # Commit changes to the database
        db.session.commit()
        return redirect(url_for('admin'))

    return render_template('edit.html', job_card=job_card)

# Route to manage parts (parts.html)
@app.route('/parts', methods=['GET', 'POST'])
def manage_parts():
    if request.method == 'POST':
        # Update parts quantities (pieces sent by admin)
        for part in Part.query.all():
            quantity_sent = request.form.get(f'quantity_sent_{part.id}')
            if quantity_sent:
                # Update the quantity_sent and sync quantity_available with quantity_sent
                part.quantity_sent = int(quantity_sent)
                part.quantity_available = int(quantity_sent)  # Set available stock equal to sent pieces
                db.session.commit()

        flash('Parts updated successfully!', 'success')  # Flash success message
        return redirect(url_for('manage_parts'))
    
    # Get all parts from database
    parts = Part.query.all()
    return render_template('parts.html', parts=parts)


if __name__ == '__main__':
    app.run(debug=True)
