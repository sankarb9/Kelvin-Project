# Expense Tracker

A web-based expense tracker built with **Flask** and **MongoDB**. Users create an account, log in, and manage their own expenses. Each person sees only their own data.

## Features

- Sign up and log in with an email address or a username
- Add, edit and delete expenses (amount, category, description, date)
- Filter by month and category
- Total spend and a per-category breakdown
- Light and dark theme, works on mobile
- Passwords are stored as salted hashes, never in plain text

## Project structure

```
expense-web/
├── app.py          # Flask backend: auth, REST API, MongoDB access
├── index.html      # Main page (expenses dashboard)
├── login.html      # Sign in / create account page
└── README.md
```

`app.py` and both HTML files must be in the **same folder**.

## Requirements

- Python 3.9 or newer
- A MongoDB database: either local MongoDB or a free [MongoDB Atlas](https://www.mongodb.com/atlas) cluster
- Python packages: `flask`, `pymongo` (add `"pymongo[srv]"` if your connection string starts with `mongodb+srv://`)

## Setup

1. **Install the packages**

   ```bash
   pip install flask pymongo
   ```

2. **Set your configuration** (see the table below).

   Windows (PowerShell):
   ```powershell
   $env:MONGO_URI="mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/"
   $env:SECRET_KEY="paste-a-long-random-string"
   ```

   Mac / Linux:
   ```bash
   export MONGO_URI="mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/"
   export SECRET_KEY="paste-a-long-random-string"
   ```

3. **Start the app**

   ```bash
   python app.py
   ```

4. **Open** <http://localhost:5000/> and create an account.

## Configuration

| Variable     | Default                      | Purpose |
|--------------|------------------------------|---------|
| `MONGO_URI`  | `mongodb://localhost:27017`  | MongoDB connection string |
| `MONGO_DB`   | `expense_tracker`            | Database name |
| `SECRET_KEY` | random on each start         | Signs login sessions. Set a fixed value, or everyone is logged out whenever the server restarts |

To generate a secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Connecting to MongoDB Atlas

1. In Atlas, go to **Database → Connect → Drivers** and copy the connection string.
2. Replace `<password>` with your database user's password.
3. If the password contains special characters (`@ : / # %`), URL-encode them, for example `p@ss#1` becomes `p%40ss%231`.
4. Under **Network Access**, allow your IP address, or the connection will time out.

## Using the app

1. Open the **Create account** tab and register with an email or a username (3–30 letters, numbers, `.` `_` `-`). The password must be at least 8 characters.
2. Add expenses with the form on the left.
3. Use **Edit** and **Delete** on any row. Use the Month and Category filters above the breakdown.
4. Click **Log out** in the header when you're done. Sessions last 7 days.

## Data stored in MongoDB

| Collection | Contents |
|------------|----------|
| `users`    | `username`, `username_lower` (unique), `password_hash`, `created_at` |
| `expenses` | `id` (per-user number), `user_id`, `date` (`YYYY-MM-DD`), `category`, `amount`, `description`, `created_at` |
| `counters` | One counter per user, used to number expenses |

## API reference

All `/api/expenses` and `/api/summary` routes require a logged-in session and only touch the current user's data. Requests and responses are JSON.

| Method | Route                  | Description |
|--------|------------------------|-------------|
| POST   | `/api/register`        | Create an account and sign in. Body: `username`, `password` |
| POST   | `/api/login`           | Sign in. Body: `username`, `password` |
| POST   | `/api/logout`          | Sign out |
| GET    | `/api/me`              | Current user |
| GET    | `/api/expenses`        | List expenses. Optional query: `month=YYYY-MM`, `category=Food` |
| POST   | `/api/expenses`        | Add an expense. Body: `amount`, `category`, `description`, `date` |
| PUT    | `/api/expenses/<id>`   | Update an expense (same body as above) |
| DELETE | `/api/expenses/<id>`   | Delete an expense |
| GET    | `/api/summary`         | Totals per category. Same optional filters as the list |

Common responses: `400` invalid input, `401` not signed in or wrong credentials, `404` expense not found, `409` username already taken.

## Security notes

- Passwords are hashed with Werkzeug (scrypt).
- Session cookies are `HttpOnly` and `SameSite=Lax`.
- Always set a fixed `SECRET_KEY` outside of local testing.
- `python app.py` runs Flask's development server in debug mode. **Do not expose it to the internet.** For a public deployment, serve it over HTTPS with a production server such as gunicorn, and turn off debug mode.
- There is no email confirmation or password reset yet.

## Troubleshooting

| Problem | Likely cause and fix |
|---------|----------------------|
| **"Not Found"** page | `index.html` / `login.html` isn't next to `app.py`, or you opened a different address. Use <http://localhost:5000/> |
| "Check that MongoDB is running" | MongoDB isn't reachable. Check `MONGO_URI`, that the server is running, and (Atlas) your IP under Network Access |
| Logged out after every restart | `SECRET_KEY` is not set. Set a fixed value |
| Expenses saved before accounts were added don't show | Older expenses have no owner, so they're hidden. They are still in the `expenses` collection and can be assigned to a user with a one-time script |
| "That username is taken" | Usernames and emails are case-insensitive and must be unique |
| Page looks unstyled / wrong font | The font loads from Google Fonts. Offline, the page falls back to your system font |
