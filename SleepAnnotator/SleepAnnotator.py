import json
import pandas as pd
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# ***********************************************************************
# Helper Methods

#converts seconds into hours, minutes and seconds to make it easier to read
def format_duration(seconds): 
    if pd.isna(seconds) or seconds <= 0: return "0s"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0: return f"{h}h {m}m {s}s"
    elif m > 0: return f"{m}m {s}s"
    else: return f"{s}s"

# ***********************************************************************
# Main Route and Application Logic


# (https://www.geeksforgeeks.org/python/flask-app-routing/)
# (https://www.geeksforgeeks.org/python/flask-tutorial/)

@app.route('/', methods=['GET', 'POST'])

def index():
    if request.method == 'POST':
        action = request.form.get('action')
        log_file = request.files.get('log_file') # Gets uploaded log file
        
        edit_starts = request.form.getlist('start') #Gets start times, incl. manually edited by user
        edit_positions = request.form.getlist('position') #Gets position, incl. manually edited by user
        
        try:
            # SCENARIO A: Initial File Upload Processing
            # Reads each entry in the log file and saves them, recording the start time and the position
            
            if log_file and log_file.filename != '':
                df = pd.read_csv(log_file, header=None, skip_blank_lines=True)
                df = df.iloc[:, :2]  
                df.columns = ["Start", "Position"]
            
            # SCENARIO B: Log Edited

            # If the user clicks save, a new dataframe is made with the table data on the webpage
            elif edit_starts and edit_positions:
                df = pd.DataFrame({'Start': edit_starts, 'Position': edit_positions})
                
            else:
                return render_template('index.html', error="Error (1)") # Error Code 1, in the case this somehow fails

            # Data Cleaning and Formatting
            # Removes excess characters and converts the start times in the log into datetime objects
            df["Start"] = pd.to_datetime(df["Start"].astype(str).str.replace(r'\[.*?\]', '', regex=True).str.strip())
                        
            df["Position"] = df["Position"].astype(str).str.strip() # Stores position
            df = df.dropna(subset=['Start', 'Position']).sort_values('Start').copy() #drops broken rows and sorts
            
            if df.empty: 
                raise ValueError("Error (2)") # Error Code 2 if the dataframe is empty






            #** Application Logic **

            # Creates a clean copy of the original parsed data to be sent to page
            raw_log = df.copy()
            raw_log['Start'] = raw_log['Start'].dt.strftime('%Y-%m-%d %H:%M:%S')
            raw_log_data = raw_log.to_dict(orient='records')

            # Sets the starting stint
            first_timestamp = df["Start"].min() 

            # Finds the length of each entry by comparing start time of the current and next entry.
            # It then determines if the position changed or not and keeps track so that they can be
            # displayed in single boxes for each stint. It adds a 1 to the block ID if the position changes,
            # giving each entry a unique ID for its stint for sorting/viewing later
            df["End"] = df["Start"].shift(-1).fillna(df["Start"].iloc[-1] + pd.Timedelta(seconds=1))
            df["Block"] = (df["Position"] != df["Position"].shift(1)).cumsum()
            



            # Uses the ID to group each entry in a stint and calculates the start time of the first and the
            # end time of the last to determine stint start and end time 
            stints = df.groupby(["Block", "Position"]).agg(Start=("Start", "first"), End=("End", "last")).reset_index()
            

            # Stint Calculations
            stints["Duration_Sec"] = (stints["End"] - stints["Start"]).dt.total_seconds().fillna(0) # Stint time in seconds
            stints["Duration_Ms"] = stints["Duration_Sec"] * 1000  # Stint time in miliseconds (needed for plotly)
            stints["Duration_Str"] = stints["Duration_Sec"].apply(format_duration) # Calls format_duration function
            

            # Finds how many seconds into the log a stint starts to determine how many seconds into the log it is.
            # used to determine where to skip to in video
            stints["Start_Relative"] = (stints["Start"] - first_timestamp).dt.total_seconds()
            stints["End_Relative"] = (stints["End"] - first_timestamp).dt.total_seconds()


            # Converts date-time in the stints back to a string, as using JSON with datetime crashes. Can't be used?
            # (https://docs.jsonata.org/date-time)
            stints['Start_Str'] = stints['Start'].dt.strftime('%Y-%m-%d %H:%M:%S')
            stints['End_Str'] = stints['End'].dt.strftime('%Y-%m-%d %H:%M:%S')
            stints = stints.drop(columns=['Start', 'End']) # drops datetime formatted column
            
            # Calculates the summary showing time and % in each position
            total_time = stints["Duration_Sec"].sum() # calculates total time of log
            summary = stints.groupby("Position")["Duration_Sec"].sum().reset_index() # groups by position
            summary["%"] = ((summary["Duration_Sec"] / total_time) * 100).round(2).fillna(0) # finds % spent in each position
            summary = summary.sort_values("%", ascending=False) # sorts the % in order to display
            summary_data = summary.to_dict(orient='records') # adds to dictionary

            for row in summary_data: # for each record, puts it through the format_duration function
                row['Duration_Str'] = format_duration(row['Duration_Sec'])

            # Returns data on edit so the page doesn't need to be reloaded.
            # This is important as I can't automatically upload the video file if the page re-loads
            # to introduce new data
            # (https://www.geeksforgeeks.org/python/use-jsonify-instead-of-json-dumps-in-flask/)

            if request.headers.get('Accept') == 'application/json':
                return jsonify({
                    'stints_json': stints.to_dict(orient='records'),
                    'summary_data': summary_data,
                    'raw_log_data': raw_log_data,
                    'total_time': format_duration(total_time)
                })

            # Normal page load for initial file upload
            return render_template(
                'index.html',
                stints_json=json.dumps(stints.to_dict(orient='records')),   
                summary_data=summary_data,                                  
                raw_log_data=raw_log_data,                                  
                total_time=format_duration(total_time),                     
                has_data=True                                               
            )

        except Exception as e:
            return render_template('index.html', error=f"Error (3) - Error processing data: {str(e)}")

    return render_template('index.html', has_data=False)

if __name__ == '__main__':
    app.run(debug=True)