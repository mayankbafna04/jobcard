from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobcards.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'  # Required for flash messages
db = SQLAlchemy(app)
migrate = Migrate(app, db) 

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
    quantity_sent = db.Column(db.Integer, nullable=False, default=0)  # Pieces sent by admin
    quantity_available = db.Column(db.Integer, nullable=False, default=0)  # Available pieces

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
        
        # Get the list of parts used (only those selected in the dropdown)
        parts_used = request.form.getlist('partsUsed')  # Returns a list of selected parts

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
            parts_used=', '.join(parts_used)  # Store selected parts as a comma-separated string
        )

        # Add the new job card to the database
        db.session.add(new_job_card)
        db.session.commit()

        # Deduct from available stock (pieces) for each part used
        for part_name in parts_used:
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
    parts = Part.query.all()  # Get all parts
    return render_template('admin.html', job_cards=job_cards, parts=parts)

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
# Route for Material Management (material.html)
@app.route('/materials', methods=['GET', 'POST'])
def materials():
    if request.method == 'POST':
        # Handle the form submission and update available quantities for parts
        for part in Part.query.all():
            available_quantity = request.form.get(f'available_{part.id}')
            if available_quantity is not None:
                part.quantity_available = int(available_quantity)
        db.session.commit()
        flash('Material quantities updated successfully!', 'success')
        return redirect(url_for('materials'))

    # Get all parts
    parts = Part.query.all()

    # Create a set to store parts that are used in job cards
    used_parts = set()

    # Check which parts have been used in job cards
    job_cards = JobCard.query.all()
    for job_card in job_cards:
        used_parts.update(job_card.parts_used.split(', '))  # Add parts used in this job card

    # Only show the used parts in the template
    used_parts = list(used_parts)  # Convert the set to a list

    # Filter the parts to show only those that are used
    parts_to_display = [part for part in parts if part.name in used_parts]

    return render_template('material.html', parts=parts_to_display, used_parts=used_parts)

# Route for adding new parts
@app.route('/add_part', methods=['GET', 'POST'])
def add_part():
    if request.method == 'POST':
        # Get the part details from the form
        part_name = request.form['partName']
        quantity_sent = request.form['quantitySent']
        quantity_available = request.form['quantityAvailable']

        # Check if the part already exists in the database
        existing_part = Part.query.filter_by(name=part_name).first()
        if existing_part:
            flash('This part already exists!', 'error')
            return redirect(url_for('add_part'))

        # Create a new Part entry in the database
        new_part = Part(
            name=part_name,
            quantity_sent=int(quantity_sent),
            quantity_available=int(quantity_available)
        )

        # Add the new part to the database
        db.session.add(new_part)
        db.session.commit()
        flash('New part added successfully!', 'success')
        return redirect(url_for('materials'))  # Redirect to the materials page after adding

    return render_template('add_part.html')

# Route to update the quantities of parts
@app.route('/update_part/<int:part_id>', methods=['POST'])
def update_part(part_id):
    part = Part.query.get_or_404(part_id)

    # Get updated values from the form
    quantity_sent = request.form.get('quantitySent')
    quantity_available = request.form.get('quantityAvailable')

    if quantity_sent is not None:
        part.quantity_sent = int(quantity_sent)
    if quantity_available is not None:
        part.quantity_available = int(quantity_available)

    db.session.commit()
    flash('Part updated successfully!', 'success')
    return redirect(url_for('materials'))

# Route to delete a part
@app.route('/delete_part/<int:part_id>', methods=['POST'])
def delete_part(part_id):
    part = Part.query.get_or_404(part_id)
    db.session.delete(part)
    db.session.commit()
    flash('Part deleted successfully!', 'success')
    return redirect(url_for('materials'))


if __name__ == '__main__':
    app.run(debug=True)
