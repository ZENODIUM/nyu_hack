import streamlit as st
import pymupdf
import google.generativeai as genai
import re
import os
import ast
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from video_gen import generate_video_with_text
from youtube import get_youtube_links

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyDm9zT2nZo1KAn6vYgzNPFnx7vhql572lk"
genai.configure(api_key=GEMINI_API_KEY)

# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    doc = pymupdf.open(pdf_path)  # Using pymupdf
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n"
    return text

# Function to fetch transactions using Gemini API
def get_transactions_from_gemini(text):
    prompt = f"""
    Extract only the transactions ONLY where money is spent (not incoming money) from this bank statement, only give the data where money is reduced from the account/debited.
    The format should be:
    date (date/month),where the transaction is done(account name/description),amount spent,geographical location of the transaction (extract it from account name/description if available)
    
    IF ANY DATA IS NOT PRESENT FILL IT WITH N/A
    Example:
    12/01,Starbucks,5.00,New York
    12/02,Amazon,20.00,N/A
    
    
    Here is the bank statement text:
    {text}
    """
    model = genai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content(prompt)
    return response.text.strip() if response.text else "No transactions found."

def get_meta_data_from_gemini(text):
    prompt = f"""
    Given this bank statement details, extract the bank name from this, give in this exact format:
    bank_name: name of the bank

    the details:
    {text}
    """
    model = genai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content(prompt)
    return response.text.strip() if response.text else "No transactions found."


def get_summary_from_gemini(text):
    prompt = f"""
    Given this bank statement of the period, provide the details:
    give the output in this EXACT format dont give add other texts:
    summary: detailed summary of the transactions
    categories: [category1: total amount, category2: total amount, ...]
    financial_advice: any financial advice based on the transactions
    spending_personality: personality based on the transactions (like "The Saver," "The Splurger," "The Planner" etc.) and a line about it
    whatif_scenarios: any whatif scenarios based on the transactions(such as "What if I stopped buying coffee every day?" or "What if I invested 10% of my income?" and show the long-term impact on savings)
    financial_story: Generate a Short spending summary Story based on the categories, make sure each line has atleast 10 words! , give it in this EXACT format: ("line1.","related physical object video which I should search for on internet in one word"),("line2.","...") 
    youtube_search: single search query for money saving youtube videos based on categories and spending personality

    Example:
    summary: You spent a total of $1000 this month, with most of it going to groceries and rent.....
    categories: groceries: $500, rent: $300, entertainment: $200.....
    financial_advice: You should consider cutting down on eating out to save more money....
    spending_personality: You are "The Saver," you are good at saving money and you should continue to do so....
    whatif_scenarios: What if you stopped eating out every day? You could save $200 a month....
    financial_story: ("You spent most of your money 500$ on groceries which are essentials.","grocery"),("You should consider cutting down on eating out, as it cost you 200$.","food")
    youtube_search: Give saving money tips for groceries and food

    Here is the bank statement text:
    {text}
    """
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(prompt)
    return response.text.strip() if response.text else "No transactions found."

def parse_categories(categories_str):
    categories = {}
    for item in categories_str.split(','):
        parts = item.split(':')
        if len(parts) == 2:
            category = parts[0].strip()
            amount = parts[1].strip().replace('$', '').replace(',', '')
            try:
                categories[category] = float(amount)
            except ValueError:
                pass
    return categories

def create_donut_chart(categories):
    fig = go.Figure(data=[go.Pie(labels=list(categories.keys()), values=list(categories.values()), hole=.3)])
    fig.update_layout(
        title_text="Spending Categories",
        annotations=[dict(text='Expenses', x=0.5, y=0.5, font_size=20, showarrow=False)]
    )
    return fig



def create_timeline_chart(transactions):
    # Convert transactions to a DataFrame
    df = pd.DataFrame(transactions, columns=['Date', 'Name', 'Amount', 'Place'])
    
    # Convert Date to datetime and Amount to float
    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m')
    df['Amount'] = df['Amount'].str.replace('$', '').str.replace(',', '').astype(float)
    
    # Group by date and sum the amounts
    daily_sum = df.groupby('Date')['Amount'].sum().reset_index()
    
    # Sort by date
    daily_sum = daily_sum.sort_values('Date')
    
    # Create the timeline chart
    fig = px.line(daily_sum, x='Date', y='Amount', 
                  title="Daily Spending Timeline", 
                  labels={"Date": "Date", "Amount": "Total Amount Spent ($)"})
    
    fig.update_traces(line_color="#FFA07A", mode='lines+markers', 
                      hovertemplate='Date: %{x|%d/%m}<br>Total Amount: $%{y:.2f}')
    fig.update_layout(xaxis_title="Date", yaxis_title="Total Amount Spent ($)")
    
    return fig


def main():
    st.set_page_config(layout="wide", page_title="Bank Statement Analyzer", page_icon="💰")

    if "file_uploaded" not in st.session_state:
        st.session_state.file_uploaded = False  # Tracks if a file has been uploaded
    if "file_path" not in st.session_state:
        st.session_state.file_path = None  # Stores the path of the uploaded file
    if "extracted_text" not in st.session_state:
        st.session_state.extracted_text = None  # Stores extracted text from the PDF

    # Sidebar chat box
    with st.sidebar:
        st.title("Piggylytics Bot")
        st.markdown('''
                    <div style="width: 100%; display: flex; justify-content: center; align-items: center;">
  <img src="https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExbzNyemtoY2gyZzU1ZzJhOW5vend4Y2h2bmtub2IybjZycXY2ZHUxMCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/Rez1ZTAxg6v1wj5CDd/giphy.gif" alt="Loading GIF" style="width: 50%; height: 50%;">
</div>

                    ''',unsafe_allow_html=True
                    )
        st.divider()
        prompt = st.chat_input("Say something")
        
        if prompt:
            with st.chat_message("user"):
                st.write(f"User: {prompt}")
            
            with st.chat_message("assistant"):
                if prompt.lower() == "hi":
                    st.write("Hie!, Piggy here 🐷")
                
                elif prompt.lower() == "tutorial":
                    st.write("📖 *Pigylitcs Bot Tutorial:*\n"
                            "- Upload your bank statement 📄\n"
                            "- Get insights with AI 📊\n"
                            "- View spending categories 🏦\n"
                            "- Receive financial advice 💡\n"
                            "- Generate a video summary 🎥\n"
                            "Need more help? Just ask! 😊")

                elif prompt.lower() == "features":
                    st.write("✨ *Pigylitcs Bot Features:*\n"
                            "- 🏦 *Transaction Analysis:* Categorizes expenses\n"
                            "- 📊 *Data Visualization:* Graphs & spending trends\n"
                            "- 🤖 *AI-Powered Insights:* Personalized summaries\n"
                            "- 💡 *Financial Advice:* AI-generated saving tips\n"
                            "- 🎥 *Video Summary:* Auto-generated financial reports\n"
                            "- 🔎 *What-If Scenarios:* Simulated saving strategies\n"
                            "- 📺 *YouTube Tips:* Fetches relevant financial advice videos")

                elif prompt.lower() == "future":
                    st.write("🔮 *Future Enhancements:*\n"
                            "- 🏦 *Auto-fetch Bank Statements* (Gmail API integration)\n"
                            "- 🤖 *Advanced AI Predictions* (Detect spending patterns)\n"
                            "- 📈 *Custom Budget Goals* (Set and track savings goals)\n"
                            "- 💰 *Automated Investment Insights* (Suggest better money habits)\n"
                            "- 🔄 *Multi-Account Tracking* (Monitor finances from multiple banks)")

                else:
                    st.write("Oops! 🐷 I didn't get that. Try:\n"
                            "- hi for a greeting\n"
                            "- tutorial for how to use Pigylitcs Bot\n"
                            "- features to see all available features\n"
                            "- future to check upcoming enhancements\n")
            
        

    st.title("🏦 Bank Statement Analyzer")
    

    uploaded_file = st.file_uploader("Upload Bank Statement PDF", type="pdf")
    if uploaded_file is not None and not st.session_state.file_uploaded:
        file_path = os.path.join("uploads", uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        extracted_text = extract_text_from_pdf(file_path)
        meta_data = extracted_text[:1000]

        transactions = get_transactions_from_gemini(extracted_text)
        lines = transactions.strip().split("\n")
        result = [line.split(",") for line in lines]
        extracted = [f"{item[1].strip()} {item[2].strip()}" for item in result]
        result_string = "\n".join(extracted)

        


        transactions_summary = get_summary_from_gemini(result_string)

        summary_match = re.search(r'summary:\s*(.*?)(?=\n|$)', transactions_summary, re.DOTALL)
        summary = summary_match.group(1) if summary_match else "Summary not available."

        financial_story_match = re.search(r'financial_story:\s*(.*)', transactions_summary)
        youtubequery = re.findall(r'youtube_search:\s*(.*)', transactions_summary)
        youtubequery = " ".join(youtubequery)

        if financial_story_match:
            financial_story_content = financial_story_match.group(1)
        else:
            financial_story_content = ""

        financial_story_list = ast.literal_eval(f"[{financial_story_content}]")
        combined_string = ", ".join([item[0] for item in financial_story_list])

        col1, col2 = st.columns([1, 2])

        with col1:

            st.subheader("📊 Transactions Summary")

            st.warning(summary)


        with col2:

            st.subheader("🎥 Video Summary")

            second_parts_list = [item[1] for item in financial_story_list]
            video_path = generate_video_with_text(combined_text=combined_string, second_parts=second_parts_list)
            st.video(video_path)
  
        
        st.subheader("📈 Spending Analysis")
        st.divider()
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            
            st.subheader("Category Breakdown")
            categories_match = re.search(r'categories:\s*(.*?)(?=\n|$)', transactions_summary, re.DOTALL)
            if categories_match:
                categories_str = categories_match.group(1)
                categories_dict = parse_categories(categories_str)
                if categories_dict:
                    donut_chart = create_donut_chart(categories_dict)
                    st.plotly_chart(donut_chart, use_container_width=True)
                else:
                    st.warning("Unable to create category chart due to parsing issues.")
            else:
                st.warning("Category information not found in the summary.")


        with chart_col2:
            st.subheader("📅 Recent Spending Timeline")
            if result:
                timeline_chart = create_timeline_chart(result)
                st.plotly_chart(timeline_chart, use_container_width=True)
            else:
                st.write("No transaction data available for timeline.")

        st.subheader("💡 Financial Insights")
        st.divider()
        card_col1, card_col2, card_col3 = st.columns(3)

        with card_col1:
            st.subheader("💰 Financial Advice")
            
            financial_advice = re.search(r'financial_advice:\s*(.*?)(?=\n|$)', transactions_summary, re.DOTALL)
            if financial_advice:
                st.info(financial_advice.group(1))
            else:
                st.info("No financial advice available.")

        with card_col2:

            st.subheader("🤔 What If Scenarios")
            
            whatif_scenarios = re.search(r'whatif_scenarios:\s*(.*?)(?=\n|$)', transactions_summary, re.DOTALL)
            if whatif_scenarios:
                st.error(whatif_scenarios.group(1))
            else:
                st.error("No 'What If' scenarios available.")


        with card_col3:
            st.subheader("🎥 Suggested YouTube Videos")
            
            youtubelist = get_youtube_links("AIzaSyA1yN2irDyHuUXTOGPGzskqEjsw5vwDUxU", youtubequery)
            if youtubelist:
                for item in youtubelist[:3]:
                    st.write(f"- {item}")
            else:
                st.success("No YouTube video suggestions available.")


        st.subheader("📌 Location Based Summary")
        st.divider()
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderServiceError

        # Initialize geolocator
        geolocator = Nominatim(user_agent="my_app")

        # Create a dictionary to store cached coordinates
        location_cache = {}

        # Function to get coordinates with error handling, retry, and caching
        def get_coordinates(place, max_attempts=3):
            # Check if the place is already in the cache
            if place in location_cache:
                return location_cache[place]
            
            for attempt in range(max_attempts):
                try:
                    location = geolocator.geocode(place)
                    if location:
                        # Cache the result
                        location_cache[place] = (location.latitude, location.longitude)
                        return location.latitude, location.longitude
                except (GeocoderTimedOut, GeocoderServiceError):
                    if attempt == max_attempts - 1:
                        st.warning(f"Failed to geocode {place} after {max_attempts} attempts")
            return None, None

        # Convert place names to coordinates
        coordinates = []
        for transaction in result:
            lat, lon = get_coordinates(transaction[3])
            if lat and lon:
                coordinates.append([transaction[0], transaction[1], float(transaction[2]), lat, lon])

        # Convert to DataFrame
        df = pd.DataFrame(coordinates, columns=['Date', 'Name', 'Amount', 'Latitude', 'Longitude'])

        # Group by Latitude and Longitude, summing the amounts
        grouped = df.groupby(['Latitude', 'Longitude'])['Amount'].sum().reset_index()

        # Add a size column for circle size based on the amount
        grouped['Size'] = grouped['Amount'] / grouped['Amount'].max() * 1000  # Adjust multiplier as needed

        # Rename the columns to match Streamlit's requirements
        grouped = grouped.rename(columns={'Latitude': 'lat', 'Longitude': 'lon'})

        # Display the map
        st.map(grouped)

        # Optionally, display the data table below the map
        coord_to_place = {(lat, lon): place for place, (lat, lon) in location_cache.items()}

        # Create a new DataFrame with Place and Amount
        place_amount_df = pd.DataFrame({
            'Place': [coord_to_place.get((row['lat'], row['lon']), 'Unknown') for _, row in grouped.iterrows()],
            'Amount': grouped['Amount']
        })

        # Display the data table with Place and Amount
        st.write("Transactions by Place:")
        st.table(place_amount_df)


    
        st.balloons()
        os.remove(file_path)
       
    

if __name__ == "__main__":
    os.makedirs("uploads", exist_ok=True)
    main()