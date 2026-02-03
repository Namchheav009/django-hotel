# QUICK START TESTING GUIDE

## 🚀 How to Test the New Features

### 1. Start the Server
```bash
cd d:\test-asp\django-hotel\Hotelproject
python manage.py runserver
```

### 2. User Profile Page
- **URL:** `http://localhost:8000/profile/`
- **Requirements:** Must be logged in
- **Test:**
  - Click Profile tab - see personal info
  - Click "Edit" button - update your name/phone
  - View "My Bookings" tab - see booking history
  - View "My Reviews" tab - see your ratings
  - Click "Settings" tab - try changing password

### 3. Enhanced Room Details
- **URL:** `http://localhost:8000/room/<room_id>/`
- **Features to test:**
  - View improved room information card
  - See amenities list with icons
  - Check house rules section
  - Try booking button

### 4. Rate a Room
- **URL:** `http://localhost:8000/room/<room_id>/rate/`
- **Requirements:** Must be logged in
- **Test:**
  - Click stars to rate (1-5)
  - Fill in detailed ratings (cleanliness, comfort, amenities)
  - Write a review (max 1000 chars)
  - Submit the form

### 5. Admin Reports
- **URL:** `http://localhost:8000/admin/reports/`
- **Requirements:** Must be admin/staff user
- **Test:**
  - View revenue, bookings, occupancy stats
  - Check revenue trend chart
  - See top booked rooms
  - View top services
  - Check guest status breakdown

### 6. Admin Sidebar
- **URL:** `http://localhost:8000/admin/dashboard/`
- **New Link:** "Reports" - click to go to analytics

---

## 📋 Test Checklist

### User Features
- [ ] Login with test user account
- [ ] Visit `/profile/` page
- [ ] View profile information
- [ ] Click "Edit" modal and update info
- [ ] Check "My Bookings" tab
- [ ] View booking details
- [ ] Rate a room (if checkout status)
- [ ] View your reviews in "My Reviews" tab
- [ ] Change password in "Settings" tab

### Admin Features
- [ ] Login with admin account
- [ ] Go to admin dashboard
- [ ] Click "Reports" in sidebar
- [ ] View metrics and statistics
- [ ] Check revenue chart loads
- [ ] See top rooms and services tables
- [ ] View guest status statistics

### Navigation
- [ ] Profile link appears in user menu
- [ ] Reports link appears in admin sidebar
- [ ] All new URLs are accessible
- [ ] Proper redirects when not authenticated

---

## 🐛 Common Issues & Solutions

### Issue: Profile page shows "Page not found"
**Solution:** Make sure you're logged in. The view requires `@login_required`

### Issue: Reports page won't load
**Solution:** Make sure you're an admin user. Check if Chart.js CDN is loading.

### Issue: Forms not validating
**Solution:** Check browser console for JavaScript errors. Verify Bootstrap is loaded.

### Issue: Rating not saved
**Solution:** Check if room exists in database. Check Django error logs.

---

## 📊 Sample Test Data

If you need test data, create them through Django admin:

1. Create users (with different roles: Customer, Admin)
2. Create rooms with prices
3. Create reservations between users and rooms
4. Create payments for reservations
5. Mark reservations as "Checked Out"
6. Then test rating system

---

## 🔍 Key Files Modified

- `hotel/views.py` - Added 6 new views
- `hotel/forms.py` - Added 2 new forms
- `hotel/urls.py` - Added 7 new URL patterns
- `hotel/template/hotel/html/base.html` - Updated navbar
- `hotel/template/hotel/html/room_detail.html` - Enhanced design
- `hotel/template/hotel/html/user_profile.html` - NEW
- `hotel/template/hotel/admin/reports.html` - NEW
- `hotel/template/hotel/admin/admin_base.html` - Added Reports link

---

## ✅ Verification Commands

```bash
# Check for syntax errors
python manage.py check

# Run migrations (if needed)
python manage.py migrate

# Create test user
python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.create_user('testuser', 'test@example.com', 'password123')
>>> user.is_staff = True
>>> user.save()

# Exit shell
>>> exit()
```

---

## 🎯 Feature Walkthrough

### User Profile Flow
1. User clicks profile icon in navbar
2. Select "My Profile" dropdown option
3. User sees `/profile/` page
4. Can view personal info, bookings, reviews
5. Can edit profile via modal
6. Can change password
7. Can rate rooms from bookings

### Admin Reports Flow
1. Admin logs in
2. Goes to admin dashboard
3. Clicks "Reports" in sidebar
4. Sees analytics page with:
   - Key metrics (Revenue, Bookings, Occupancy, Rating)
   - Revenue chart
   - Top rooms table
   - Top services table
   - Guest statistics

---

## 📝 Notes

- All new features use existing models (no DB changes)
- Forms have client-side validation ready
- All templates use Bootstrap 5.3.0
- Font Awesome icons included
- Responsive design for mobile
- Chart.js loaded from CDN

---

**Ready to test!** Start the server and visit the URLs above.

For any issues, check Django logs: `python manage.py runserver --verbosity=2`
