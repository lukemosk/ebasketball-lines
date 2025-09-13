# setup_visualization.sh
#!/bin/bash
# Setup script for the middle analysis visualization

echo "Setting up eBasketball Middle Analysis Visualization"
echo "=================================================="

# Install Python dependencies
echo "Installing Python dependencies..."
pip install flask flask-cors

# Check if database exists
if [ -f "data/ebasketball.db" ]; then
    echo "✅ Database found: data/ebasketball.db"
else
    echo "❌ Database not found. Make sure data/ebasketball.db exists"
    exit 1
fi

# Create the backend script
echo "Backend script ready: middle_analysis_backend.py"

# Instructions for the React component
echo ""
echo "📋 Setup Instructions:"
echo "======================"
echo ""
echo "1. Start the backend server:"
echo "   python middle_analysis_backend.py"
echo ""
echo "2. The backend will run on http://localhost:5000"
echo "   Test it by visiting: http://localhost:5000/api/database-stats"
echo ""
echo "3. The React visualization component is ready to use."
echo "   It will fetch real data from your database."
echo ""
echo "4. If you need to set up a React app:"
echo "   npx create-react-app middle-viz"
echo "   cd middle-viz"
echo "   npm install recharts"
echo "   # Then replace src/App.js with the React component"
echo ""
echo "🔧 Troubleshooting:"
echo "=================="
echo "- Backend error: Check that data/ebasketball.db exists and has data"
echo "- CORS error: Make sure flask-cors is installed"
echo "- No data: Run your tracker to collect more games"
echo ""
echo "Ready to visualize your spread middle data! 📊"