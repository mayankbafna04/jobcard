

from flask import Flask, render_template, request, redirect, send_file, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
import logging
import pandas as pd
from io import BytesIO




app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'  # Required for flash messages
db = SQLAlchemy(app)
migrate = Migrate(app, db) 

# Inward Model
class Inward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    model_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(15), nullable=False)
    vehicle_number = db.Column(db.String(20), nullable=False)
    jobcard_number = db.Column(db.String(50), nullable=False)
    customers_voice = db.Column(db.String(500), nullable=False)
    charger_present = db.Column(db.String(5), nullable=False)
    charger_number = db.Column(db.String(50))
    date = db.Column(db.String(20), nullable=False)

    def __repr__(self):
        return f"Inward('{self.customer_name}', '{self.phone_number}', '{self.jobcard_number}')"

# Job Card Model
class JobCard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    phone_no = db.Column(db.String(15), nullable=False)
    model_name = db.Column(db.String(100), nullable=False)
    vehicle_no = db.Column(db.String(20), nullable=False)
    job_card_number = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.String(200), nullable=False)
    charger_present = db.Column(db.String(5), nullable=False)
    mechanic_name = db.Column(db.String(100), nullable=False)
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


# Route for the Landing Page
@app.route('/')
def landing():
    return render_template('landing.html')

# Route for the Job Card Submission Form (index.html)
@app.route('/get_customer_details/<phone_number>')
def get_customer_details(phone_number):
    inward = Inward.query.filter_by(phone_number=phone_number).first()
    if inward:
        return {
            'customer_name': inward.customer_name,
            'model_name': inward.model_name,
            'vehicle_number': inward.vehicle_number
        }
    return {}

@app.route('/job_card', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Log form data for debugging
        logger.info(f"Received form data: {dict(request.form)}")
        
        # Handle form data and job card submission
        # Convert date to yyyy-mm-dd format
        input_date = request.form['date']
        try:
            # Parse date in various formats and convert to yyyy-mm-dd
            if '-' in input_date:
                parts = input_date.split('-')
                if len(parts[0]) == 4:  # Already yyyy-mm-dd
                    date = input_date
                elif len(parts) == 3 and len(parts[2]) == 4:  # dd-mm-yyyy
                    date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                else:
                    raise ValueError("Invalid date format")
            elif '/' in input_date:  # dd/mm/yyyy
                parts = input_date.split('/')
                if len(parts) == 3 and len(parts[2]) == 4:
                    date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                else:
                    raise ValueError("Invalid date format")
            else:
                raise ValueError("Invalid date format")
            
            # Validate the converted date
            datetime.strptime(date, '%Y-%m-%d')
            logger.debug(f"Successfully parsed date: {input_date} -> {date}")
            
        except ValueError as e:
            logger.error(f"Date parsing error: {e} for input: {input_date}")
            flash('Invalid date format. Please use yyyy-mm-dd, dd-mm-yyyy, or dd/mm/yyyy', 'error')
            return redirect(url_for('index'))
            
        customer_name = request.form['customerName']
        job_card_number = request.form['jobCardNumber']
        description = request.form['description']
        amount = request.form['amount']
        payment_mode = request.form['paymentMode']
        parts_used = request.form.getlist('partsUsed')  # Get selected parts list

        # Check if job card number already exists
        existing_job_card = JobCard.query.filter_by(job_card_number=job_card_number).first()
        if existing_job_card:
            flash('Job card number already exists! Please enter a unique Job Card Number.', 'error')
            return redirect(url_for('index'))  # Redirect back to form if exists

        # Create new job card and add to database
        new_job_card = JobCard(
            date=date,
            customer_name=customer_name,
            phone_no=request.form['phoneNo'],
            model_name=request.form['modelName'],
            vehicle_no=request.form['vehicleNo'],
            job_card_number=job_card_number,
            description=description,
            charger_present=request.form['chargerPresent'],
            mechanic_name=request.form['mechanicName'],
            amount=amount,
            payment_mode=payment_mode,
            parts_used=', '.join(parts_used)  # Store parts used as a comma-separated string
        )
        # Add logging for debugging
        logger.info(f"Adding new job card: {new_job_card}")
        db.session.add(new_job_card)
        
        try:
            # Deduct parts from inventory
            for part_name in parts_used:
                part = Part.query.filter_by(name=part_name).first()
                if not part:
                    logger.error(f"Part not found: {part_name}")
                    flash(f'Error: Part {part_name} not found in inventory', 'error')
                    db.session.rollback()
                    return redirect(url_for('index'))
                
                if part.quantity_available <= 0:
                    logger.error(f"Insufficient quantity for part: {part_name}")
                    flash(f'Error: Insufficient quantity for part {part_name}', 'error')
                    db.session.rollback()
                    return redirect(url_for('index'))
                
                part.quantity_available -= 1
                logger.info(f"Deducted 1 from {part_name}. New quantity: {part.quantity_available}")
            
            # Commit both job card and part updates
            db.session.commit()
            logger.info("Job card and part updates successfully committed to database")
        except Exception as e:
            logger.error(f"Error committing changes: {str(e)}")
            db.session.rollback()
            flash('Error saving job card and updating inventory', 'error')
            return redirect(url_for('index'))


        flash('Job Card successfully submitted!', 'success')
        return redirect(url_for('index'))  # Redirect to `index` after submitting the form

    # Render `index.html` if it's a GET request
    parts = Part.query.all()
    return render_template('index.html', parts=parts)  # This will serve the `index.html` template

import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging
# Route for the Admin Page (admin.html)
@app.route('/admin')
def admin():
    job_cards = JobCard.query.all()  # Get all job cards
    parts = Part.query.all()  # Get all parts
    return render_template('admin.html', job_cards=job_cards, parts=parts, datetime=datetime)

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

    # Get all parts and show them in the materials page
    parts = Part.query.all()
    return render_template('material.html', parts=parts)

# Route for adding new parts
@app.route('/add_part', methods=['GET', 'POST'])
def add_part():
    if request.method == 'POST':
        # Get the part details from the form
        part_name = request.form['partName']
        quantity_sent = int(request.form['quantitySent'])
        quantity_available = int(request.form['quantityAvailable'])

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

def get_admin_data_by_month(month=None):
    query = JobCard.query
    if month:
        query = query.filter(db.func.strftime('%Y-%m', JobCard.date) == month)
    
    job_cards = query.all()
    
    return [
        {
            "Date": job_card.date,
            "Customer Name": job_card.customer_name,
            "Job Card Number": job_card.job_card_number,
            "Description": job_card.description,
            "Amount": job_card.amount,
            "Payment Mode": job_card.payment_mode,
            "Parts Used": job_card.parts_used
        }
        for job_card in job_cards
    ]

@app.route('/download_admin_data')
def download_admin_data():
    month = request.args.get('month')
    admin_data = get_admin_data_by_month(month)

    # Create a DataFrame from the fetched data
    df = pd.DataFrame(admin_data)

    # Format the date column
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')

    # Create a BytesIO buffer for the Excel file
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Admin Data')
    output.seek(0)

    # Set appropriate filename
    filename = f'Admin_Data_{month}.xlsx' if month else 'Admin_Data_All.xlsx'

    # Send the Excel file as a response
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# Route for the Inward Index Page (inward_index.html)
@app.route('/inward_index', methods=['GET', 'POST'])
def inward_index():
    return render_template('inward_index.html')

# API endpoint to check jobcard number uniqueness
@app.route('/api/check-jobcard')
def check_jobcard():
    jobcard_number = request.args.get('jobcard')
    if not jobcard_number:
        return {'exists': False}
    
    existing = Inward.query.filter_by(jobcard_number=jobcard_number).first()
    return {'exists': existing is not None}

# Route to handle inward form submission
@app.route('/submit_inward', methods=['POST'])
def submit_inward():
    # Get form data
    customer_name = request.form['customer_name']
    model_name = request.form['model_name']
    phone_number = request.form['phone_number']
    jobcard_number = request.form['jobcard_number']
    
    # Validate phone number length
    if len(phone_number) != 10 or not phone_number.isdigit():
        flash('Phone number must be exactly 10 digits', 'error')
        return redirect(url_for('inward_index'))
    
    # Validate jobcard number uniqueness
    existing_jobcard = Inward.query.filter_by(jobcard_number=jobcard_number).first()
    if existing_jobcard:
        flash('Jobcard number must be unique', 'error')
        return redirect(url_for('inward_index'))
    
    vehicle_number = request.form['vehicle_number']
    customers_voice = request.form['customers_voice']
    charger_present = request.form['charger_present']
    charger_number = request.form.get('charger_number', '')
    
    # Convert date to yyyy-mm-dd format
    input_date = request.form['date']
    try:
        # Parse date in various formats and convert to yyyy-mm-dd
        if '-' in input_date:
            parts = input_date.split('-')
            if len(parts[0]) == 4:  # Already yyyy-mm-dd
                date = input_date
            elif len(parts) == 3 and len(parts[2]) == 4:  # dd-mm-yyyy
                date = f"{parts[2]}-{parts[1]}-{parts[0]}"
            else:
                raise ValueError("Invalid date format")
        elif '/' in input_date:  # dd/mm/yyyy
            parts = input_date.split('/')
            if len(parts) == 3 and len(parts[2]) == 4:
                date = f"{parts[2]}-{parts[1]}-{parts[0]}"
            else:
                raise ValueError("Invalid date format")
        else:
            raise ValueError("Invalid date format")
        
        # Validate the converted date
        datetime.strptime(date, '%Y-%m-%d')
        logger.debug(f"Successfully parsed date: {input_date} -> {date}")
        
    except ValueError as e:
        logger.error(f"Date parsing error: {e} for input: {input_date}")
        flash('Invalid date format. Please use yyyy-mm-dd, dd-mm-yyyy, or dd/mm/yyyy', 'error')
        return redirect(url_for('inward_index'))

    # Save the inward data to the database
    new_inward = Inward(
        customer_name=customer_name,
        model_name=model_name,
        phone_number=phone_number,
        vehicle_number=vehicle_number,
        jobcard_number=jobcard_number,
        customers_voice=customers_voice,
        charger_present=charger_present,
        charger_number=charger_number,
        date=date
    )
    db.session.add(new_inward)
    db.session.commit()

    flash('Inward data successfully submitted!', 'success')
    return redirect(url_for('inward_index'))  # Redirect back to inward index

# Route to display inward data in admin panel
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.route('/inward_admin')
def inward_admin():
    inwards = Inward.query.all()  # Fetch all inward records from the database
    return render_template('inward_admin.html', inwards=inwards, datetime=datetime)

def get_inward_data_by_month(month=None):
    query = Inward.query
    if month:
        query = query.filter(db.func.strftime('%Y-%m', Inward.date) == month)
    
    inwards = query.all()
    
    return [
        {
            "Customer Name": inward.customer_name,
            "Model Name": inward.model_name,
            "Phone Number": inward.phone_number,
            "Vehicle Number": inward.vehicle_number,
            "Jobcard Number": inward.jobcard_number,
            "Customer's Voice": inward.customers_voice,
            "Charger Present": inward.charger_present,
            "Charger Number": inward.charger_number,
            "Date": inward.date
        }
        for inward in inwards
    ]

@app.route('/download_inward_data')
def download_inward_data():
    month = request.args.get('month')  # Get the selected month
    inward_data = get_inward_data_by_month(month)  # Fetch data for the month

    # Create a DataFrame from the fetched data
    df = pd.DataFrame(inward_data)

    # Format the date column
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')

    # Create a BytesIO buffer for the Excel file
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inward Data')
    output.seek(0)

    # Set appropriate filename
    filename = f'Inward_Data_{month}.xlsx' if month else 'Inward_Data_All.xlsx'

    # Send the Excel file as a response
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

if __name__ == '__main__':
    app.run(debug=True)
