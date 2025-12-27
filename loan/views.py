from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, update_session_auth_hash
from django.contrib import messages
from .forms import RegisterForm, LoginForm, ProfileUpdateForm, WithdrawalForm
from .models import Customer, SavingsOption, WithdrawalRequest
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_backends
from django.contrib.auth.forms import PasswordChangeForm

def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid email or password')
    else:
        form = LoginForm()
    return render(request, 'loan/login.html', {'form': form})

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            customer = form.save()
            user = customer.user
            backend = get_backends()[0]
            user.backend = f'{backend.__module__}.{backend.__class__.__name__}'
            login(request, user)
            return redirect('dashboard')
    else:
        form = RegisterForm()
    return render(request, 'loan/register.html', {'form': form})

@login_required
def dashboard(request):
    customer = get_object_or_404(Customer, user=request.user)
    
    # Initialize loan limit if not set
    if customer.loan_limit == 0:
        customer.assign_loan_limit()
    
    # Get all savings options
    savings_options = SavingsOption.objects.all()
    
    # Handle withdrawal request
    if request.method == 'POST' and 'withdraw' in request.POST:
        form = WithdrawalForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            phone_number = form.cleaned_data['phone_number']
            
            if amount > customer.savings_balance:
                # Calculate the shortfall
                shortfall = amount - customer.savings_balance
                messages.error(
                    request, 
                    f'You need Ksh {shortfall:.2f} more to withdraw Ksh {amount:.2f}. '
                    f'Your current savings: Ksh {customer.savings_balance:.2f}'
                )
                # Store the attempted withdrawal amount in session
                request.session['attempted_withdrawal'] = float(amount)
                request.session['required_savings'] = float(shortfall)
                request.session['current_savings'] = float(customer.savings_balance)
                return redirect('savings_page')   
            else:
                # Create withdrawal request
                WithdrawalRequest.objects.create(
                    customer=customer,
                    amount=amount,
                    phone_number=phone_number
                )
                messages.success(request, 'Withdrawal request submitted successfully!')
                return redirect('dashboard')
    else:
        form = WithdrawalForm(initial={
            'phone_number': customer.phone_number
        })
    
    return render(request, 'loan/dashboard.html', {
        'customer': customer,
        'savings_options': savings_options,
        'withdrawal_form': form,
        'payment_link': 'https://me.nestlink.co.ke/Maramkopo'
    })

def home(request):
    return render(request, 'loan/home.html')

@login_required
def apply_loan(request):
    if request.method == 'POST':
        customer = get_object_or_404(Customer, user=request.user)
        messages.success(request, "Loan application submitted successfully!")
        return redirect('loan_status')
    return render(request, 'loan/apply_loan.html')

@login_required
def profile_view(request):
    customer = get_object_or_404(Customer, user=request.user)
    
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=customer)
    
    return render(request, 'loan/profile.html', {'form': form})

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'loan/change_password.html', {'form': form})

@login_required
def loan_status(request):
    customer = get_object_or_404(Customer, user=request.user)
    return render(request, 'loan/status.html', {
        'customer': customer,
        'payment_link': "https://checkoutjpv2.jambopay.com/lipa/paybill/16525439"
    })

@login_required
def repayment(request):
    return render(request, 'loan/repayment.html')

@login_required
def process_savings(request):
    if request.method == 'POST':
        option_id = request.POST.get('savings_option')
        try:
            option = SavingsOption.objects.get(id=option_id)
            # Process payment here (using your existing payment system)
            # After successful payment:
            customer = request.user.customer
            customer.savings_balance += option.savings
            customer.save()
            
            # Clear any attempted withdrawal session data if it exists
            if 'attempted_withdrawal' in request.session:
                attempted_amount = request.session.pop('attempted_withdrawal', None)
                required_savings = request.session.pop('required_savings', None)
                
                # Check if the user now has enough for their attempted withdrawal
                if attempted_amount and customer.savings_balance >= attempted_amount:
                    messages.success(request, 
                        f'Successfully added Ksh {option.savings} to your savings! '
                        f'You now have Ksh {customer.savings_balance:.2f}. '
                        'You can now complete your withdrawal request.'
                    )
                else:
                    messages.success(request, f'Successfully added Ksh {option.savings} to your savings!')
            else:
                messages.success(request, f'Successfully added Ksh {option.savings} to your savings!')
                
        except SavingsOption.DoesNotExist:
            messages.error(request, 'Invalid savings option selected')
    return redirect('dashboard')

@login_required
def savings_page(request):
    savings_options = SavingsOption.objects.all()
    
    # Get the attempted withdrawal info from session
    attempted_withdrawal = request.session.get('attempted_withdrawal')
    required_savings = request.session.get('required_savings')
    current_savings = request.session.get('current_savings')
    
    # Get customer's current savings balance (in case it changed)
    customer = get_object_or_404(Customer, user=request.user)
    
    return render(request, 'loan/savings.html', {
        'savings_options': savings_options,
        'attempted_withdrawal': attempted_withdrawal,
        'required_savings': required_savings,
        'current_savings': current_savings or customer.savings_balance,
        'customer': customer  # Pass customer object for any other needed info
    })