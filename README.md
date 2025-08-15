# O-1 Visa Profile Assessment System

A comprehensive AI-powered system for analyzing and ranking professional profiles for O-1 visa compatibility using LinkedIn data and GPT-4o-mini intelligent assessment.

## 🚀 Features

- **LinkedIn Profile Discovery**: Automatically finds LinkedIn URLs using Tavily Search API
- **Professional Data Scraping**: Extracts comprehensive LinkedIn profile data via BrightData API
- **AI-Powered Assessment**: Uses GPT-4o-mini for intelligent O-1 visa scoring based on LinkedIn-specific criteria
- **Smart URL Normalization**: Handles regional LinkedIn URLs and validates format
- **Real-time Processing**: Async pipeline with detailed logging and status tracking
- **Interactive Dashboard**: Modern web interface for profile management and ranking visualization
- **RESTful API**: Complete FastAPI backend with comprehensive endpoints

## 🏗️ Architecture

### New LinkedIn-Based Pipeline (v2.0)
```
CSV Upload → LinkedIn Discovery → BrightData Scraping → GPT Assessment → Ranking
```

### Key Components
- **FastAPI Backend**: Modern async web framework
- **SQLAlchemy 2.x**: Database ORM with SQLite
- **Pydantic v2**: Data validation and serialization
- **Tavily API**: LinkedIn URL discovery
- **BrightData API**: LinkedIn profile scraping
- **OpenAI GPT-4o-mini**: Intelligent O-1 assessment

## 📊 O-1 Assessment Criteria

The system evaluates profiles based on LinkedIn-visible data:

1. **Professional Seniority** (1-10): VP, Director, CTO, Founder, Principal, Senior titles
2. **Company Prestige** (1-10): FAANG, Fortune 500, unicorns, notable startups
3. **Career Progression** (1-10): Visible promotions and increasing responsibilities
4. **Professional Network** (1-10): LinkedIn connections (500+ is good), quality recommendations
5. **Skills & Expertise** (1-10): Technical certifications, patents, specialized skills

## 🛠️ Installation

### Prerequisites
- Python 3.11+
- Virtual environment (recommended)

### Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/one_project.git
cd one_project

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables
```bash
# Required API Keys
OPENAI_API_KEY=your_openai_api_key
TAVILY_API_KEY=your_tavily_api_key
BRIGHTDATA_API_KEY=your_brightdata_api_key

# Optional Configuration
DEBUG=True
LOG_LEVEL=INFO
BRIGHTDATA_TIMEOUT=300
```

## 🚀 Usage

### Start the Server
```bash
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Access the Dashboard
Open your browser to: `http://localhost:8000/dashboard`

### API Endpoints

#### Profile Management
- `POST /profiles/upload-csv` - Upload profiles from CSV
- `POST /profiles/{profile_id}/process` - Process single profile
- `POST /profiles/process-batch` - Batch processing
- `GET /profiles/{profile_id}/assessment` - Get assessment results
- `GET /profiles/{profile_id}/processing-logs` - View processing logs

#### Rankings & Statistics
- `GET /rankings` - Get ranked profiles
- `GET /stats` - System statistics
- `GET /healthz` - Health check

### Processing Pipeline

1. **Upload CSV**: Profiles are imported from CSV file
2. **LinkedIn Discovery**: Missing LinkedIn URLs found via Tavily
3. **Data Scraping**: BrightData extracts comprehensive profile data
4. **AI Assessment**: GPT-4o-mini scores profiles on O-1 criteria
5. **Ranking**: Profiles ranked by final score

## 📈 Performance

- **Processing Time**: ~45 seconds per profile
- **Success Rate**: 95%+ (with URL normalization)
- **Timeout**: 5 minutes per profile (configurable)
- **Concurrent Processing**: Supported via async pipeline

## 🔧 Key Improvements (v2.0)

### URL Normalization
- Removes regional suffixes (`/nl`, `/br`, `/de`, etc.)
- Validates LinkedIn URL format
- Handles malformed URLs from search results

### Enhanced Timeout Management
- Increased BrightData timeout to 5 minutes
- Proper async handling of long-running operations
- Retry mechanisms for failed requests

### LinkedIn-Specific Scoring
- Criteria tailored to LinkedIn-visible data
- More realistic and achievable benchmarks
- Focus on professional seniority and company prestige

## 📊 Sample Results

Recent processing of 20 profiles:
- **3 profiles** scored ≥ 6.0 (excellent O-1 candidates)
- **3 profiles** scored 5.0-5.9 (very good candidates)
- **14 profiles** scored 3.0-4.9 (moderate candidates)

Top performers:
1. Andy Liang - 6.5/10
2. Amit Mathapati - 6.5/10  
3. Akweley Abena Okai - 6.5/10

## 🔒 Security

- API keys stored in environment variables
- No sensitive data in repository
- Input validation via Pydantic
- SQL injection protection via SQLAlchemy

## 🧪 Testing

```bash
# Run health check
curl http://localhost:8000/healthz

# Test profile processing
curl -X POST "http://localhost:8000/profiles/{profile_id}/process"

# View rankings
curl http://localhost:8000/rankings
```

## 📝 Database Schema

### Profiles Table
- Basic profile information (name, email, LinkedIn URL)
- Processing status and timestamps
- LinkedIn data (JSON)
- Social links (JSON)
- GPT assessment results (JSON)
- Final score and ranking

### Processing Logs Table
- Step-by-step processing logs
- Status tracking (started, completed, failed)
- Detailed error messages and data

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- OpenAI for GPT-4o-mini API
- Tavily for search capabilities
- BrightData for LinkedIn scraping infrastructure
- FastAPI community for excellent documentation

## 📞 Support

For questions or issues, please open a GitHub issue or contact the development team.

---

**Built with ❤️ for the AI research and startup community seeking O-1 visas**