# 🧪 Test Suite Documentation

Comprehensive test suite for the FastAPI Skeleton application using SQLite in-memory database.

---

## 📁 Test Structure

```
tests/
├── conftest.py                      # Pytest fixtures and configuration
├── test_auth_endpoints.py           # Authentication endpoint tests (87 tests)
├── test_file_endpoints.py           # File management endpoint tests (20+ tests)
├── test_token_service.py            # Token service tests (JWT lifecycle)
├── test_exception_handling.py       # Exception and error response tests
├── test_seeders.py                  # Seeder system tests
├── test_services.py                 # Service layer tests (existing)
└── README.md                        # This file
```

---

## 🚀 Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/test_auth_endpoints.py
pytest tests/test_file_endpoints.py
pytest tests/test_token_service.py
```

### Run Specific Test Class
```bash
pytest tests/test_auth_endpoints.py::TestRegisterEndpoint
pytest tests/test_file_endpoints.py::TestFileUpload
```

### Run Specific Test Function
```bash
pytest tests/test_auth_endpoints.py::TestRegisterEndpoint::test_register_success
```

### Run Tests by Marker
```bash
# Run only auth tests
pytest -m auth

# Run only file tests
pytest -m files

# Run only unit tests
pytest -m unit

# Run all except slow tests
pytest -m "not slow"
```

### Verbose Output
```bash
pytest -v
pytest -vv  # Extra verbose
```

### Show Print Statements
```bash
pytest -s
```

### Stop on First Failure
```bash
pytest -x
```

### Run Last Failed Tests
```bash
pytest --lf
```

### Run Tests in Parallel (if pytest-xdist installed)
```bash
pytest -n auto
```

---

## 📊 Test Coverage

### View HTML Test Report
After running tests, open:
```
templates/reports/test_report.html
```

### Generate Coverage Report (if pytest-cov installed)
```bash
pytest --cov=app --cov-report=html
# Open htmlcov/index.html
```

---

## 🧩 Test Components

### Fixtures (conftest.py)

**Database Fixtures:**
- `engine` - Test database engine (SQLite in-memory)
- `db_session` - Test database session (isolated per test)

**User Fixtures:**
- `test_user` - Verified test user
- `unverified_user` - Unverified test user
- `admin_user` - Admin test user

**Authentication Fixtures:**
- `auth_token` - Valid access token for test user
- `admin_token` - Valid access token for admin user

**HTTP Client Fixture:**
- `client` - Async HTTP client with database override

**File Fixtures:**
- `temp_upload_dir` - Temporary upload directory
- `sample_image_file` - Sample JPEG file
- `sample_pdf_file` - Sample PDF file

---

## 📝 Test Categories

### 1. Authentication Tests (`test_auth_endpoints.py`)

**TestRegisterEndpoint:**
- ✅ Successful registration
- ✅ Duplicate email/username handling
- ✅ Invalid email validation
- ✅ Short password validation

**TestLoginEndpoint:**
- ✅ Successful login
- ✅ Wrong password handling
- ✅ Non-existent user handling
- ✅ Unverified account handling

**TestLogoutEndpoints:**
- ✅ Single device logout
- ✅ All devices logout
- ✅ Token revocation verification
- ✅ Invalid token handling

**TestGetCurrentUser:**
- ✅ Get authenticated user
- ✅ Missing token handling
- ✅ Invalid token handling

**TestPasswordReset:**
- ✅ Forgot password request
- ✅ Non-existent email handling
- ✅ Invalid reset code handling

---

### 2. File Management Tests (`test_file_endpoints.py`)

**TestFileUpload:**
- ✅ Image upload success
- ✅ PDF upload success
- ✅ Upload with purpose tag
- ✅ Invalid file type rejection
- ✅ File size limit enforcement
- ✅ Unauthorized upload prevention

**TestListFiles:**
- ✅ List user files
- ✅ Filter by purpose
- ✅ Empty file list

**TestGetFileInfo:**
- ✅ Get file information
- ✅ Non-existent file handling
- ✅ Unauthorized access prevention

**TestDeleteFile:**
- ✅ Soft delete
- ✅ Hard delete
- ✅ Unauthorized deletion prevention
- ✅ Non-existent file handling

---

### 3. Token Service Tests (`test_token_service.py`)

**TestTokenCreation:**
- ✅ Create access token
- ✅ Create refresh token
- ✅ Token metadata storage

**TestTokenValidation:**
- ✅ Validate valid token
- ✅ Invalid signature rejection
- ✅ Revoked token rejection
- ✅ Non-existent token rejection

**TestTokenRevocation:**
- ✅ Revoke single token
- ✅ Revoke all user tokens
- ✅ Non-existent token handling

**TestTokenCleanup:**
- ✅ Cleanup expired tokens
- ✅ Preserve valid tokens

**TestTokenHashing:**
- ✅ Hash consistency
- ✅ Different inputs produce different hashes
- ✅ SHA-256 hash length

---

### 4. Exception Handling Tests (`test_exception_handling.py`)

**TestValidationErrors:**
- ✅ Invalid email format (422)
- ✅ Short password (422)
- ✅ Missing required fields (422)
- ✅ Multiple validation errors (422)

**TestAuthenticationErrors:**
- ✅ Missing token (401)
- ✅ Invalid token format (401)
- ✅ Revoked token (401)
- ✅ Wrong password (401)

**TestNotFoundErrors:**
- ✅ Non-existent user (404)
- ✅ Non-existent file (404)

**TestForbiddenErrors:**
- ✅ Access other user's file (403)

**TestBadRequestErrors:**
- ✅ Duplicate email (400)
- ✅ Invalid file type (400)

**TestResponseFormat:**
- ✅ Error response structure
- ✅ Success response structure

**TestHTTPStatusCodes:**
- ✅ 200 on success
- ✅ 400 on bad request
- ✅ 401 on unauthorized
- ✅ 403 on forbidden
- ✅ 404 on not found
- ✅ 422 on validation error

---

### 5. Seeder Tests (`test_seeders.py`)

**TestSeederDiscovery:**
- ✅ Auto-discover seeders
- ✅ Execution order sorting

**TestUserSeeder:**
- ✅ Create users
- ✅ Idempotency (run multiple times safely)
- ✅ User verification
- ✅ Password hashing

**TestSeederRunner:**
- ✅ Run all seeders
- ✅ Run specific seeder
- ✅ Non-existent seeder handling

**TestSeederEnvironmentFiltering:**
- ✅ Run in test environment
- ✅ Run in development environment
- ✅ Skip production environment
- ✅ Runner filters by environment

**TestSeederErrorHandling:**
- ✅ Commit on success
- ✅ Multiple runs safe

---

## 🔧 Configuration

### pytest.ini
```ini
[pytest]
asyncio_mode = auto           # Enable async test support
testpaths = tests             # Test directory
addopts = -v -ra -l           # Verbose, summary, local vars
markers = auth, files, etc.   # Custom test markers
```

### Test Settings (conftest.py)
```python
# Uses SQLite in-memory database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Test-specific settings
UPLOAD_DIR = "test_uploads"
MAX_UPLOAD_SIZE_MB = 5
SUPPRESS_SEND = 1  # Mock email sending
```

---

## 🎯 Best Practices

### 1. Test Isolation
- Each test uses fresh database (in-memory SQLite)
- Tests don't depend on each other
- Fixtures are function-scoped by default

### 2. Test Data
- Use fixtures for common test data
- Create minimal data needed for test
- Clean up after each test (automatic)

### 3. Assertions
```python
# ✅ Good
assert response.status_code == 200
assert data["success"] is True
assert "email" in data["data"]

# ❌ Avoid
assert response.status_code  # Not specific enough
```

### 4. Test Naming
```python
# ✅ Good - descriptive, explains what it tests
def test_register_duplicate_email_returns_400():
    pass

# ❌ Avoid - too vague
def test_register():
    pass
```

### 5. Test Organization
- Group related tests in classes
- Use descriptive class names (TestLoginEndpoint)
- One assertion per test (when possible)

---

## 📈 Adding New Tests

### 1. Create Test File
```python
# tests/test_my_feature.py
import pytest
from httpx import AsyncClient

class TestMyFeature:
    """Test my new feature"""

    @pytest.mark.asyncio
    async def test_my_feature_success(self, client: AsyncClient):
        """Test successful case"""
        response = await client.post("/api/v1/my-endpoint", json={...})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
```

### 2. Use Fixtures
```python
@pytest.mark.asyncio
async def test_with_auth(self, client: AsyncClient, auth_token: str):
    """Test with authentication"""
    response = await client.get(
        "/api/v1/protected",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
```

### 3. Add Markers
```python
@pytest.mark.slow
@pytest.mark.integration
async def test_slow_integration():
    """Long-running integration test"""
    pass
```

---

## 🐛 Debugging Tests

### Run with Debug Output
```bash
pytest -vv -s --log-cli-level=DEBUG
```

### Drop into Debugger on Failure
```bash
pytest --pdb
```

### Show Local Variables
```bash
pytest -l
```

### Run Specific Failed Test with Full Output
```bash
pytest tests/test_file.py::TestClass::test_method -vv -s
```

---

## 📚 Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [HTTPX Documentation](https://www.python-httpx.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)

---

## ✅ Test Checklist

When adding new features:

- [ ] Write tests for happy path
- [ ] Write tests for error cases
- [ ] Test authentication/authorization
- [ ] Test input validation
- [ ] Test edge cases
- [ ] Run tests locally before commit
- [ ] Check test coverage
- [ ] Update this README if needed

---

**Generated:** December 18, 2025
**Maintained by:** Development Team
