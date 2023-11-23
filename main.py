from flask import Flask, jsonify, request
from utils import *
import json
from ast import literal_eval
import numpy as np
from sklearn.manifold import TSNE
import pandas as pd

# Load the dataframe
df = pd.read_pickle('data_full.pkl')

app = Flask(__name__)


@app.route('/question', methods=['GET'])
def get_question():
    # Extract parameters
    lesson_id = request.args.get('lessonId', type=int)
    question_number = request.args.get('questionNumber', type=int)
    
    question = df.loc[question_number] 
    response = {
        "id": "17",
        "question": "Which of the following is not a requirement of GIPS for composite construction?",
        "answers": [
            "one or more portfolios.",
            "portfolios selected on an ex-post basis.",
            "portfolios managed according to a similar investment strategy."
        ],
        "correctAnswer": 0,
        "lessonFinished": True
    }

    return jsonify(response)

@app.route('/question', methods=['POST'])
def post_question():
    # Extract data from request
    data = request.json
    question_id = data.get('id')
    answer = data.get('answer')
    time_taken = data.get('timeTaken')
    response_times = data.get('responseTime')
    lesson_id = data.get('lessonId')
    
    # Compute z scores
    current_z_scores = []
    for idx,id_ in enumerate(question_id):
        question_row = df.loc[id_]
        question = question_row['question']
        response = answer[idx]
        response_time = response_times[idx]
        is_fact = bool(question_row['fact_bool']) 
        question_z_scores = question_row['z_scores']
        z_score_new = calc_z_score(question, answer, response, response_time, is_fact)
        question_z_scores.append(z_score_new)
        
        current_z_scores.append(question_z_scores)
        # Compute Q scores
        embeddings = df.loc[question_id, 'embeddings']
        Q_scores = compute_Q_scores(embeddings, current_z_scores)
        
        S_scores = 
        # Generate the summary
        summary = generate_summary(questions_str)

        # Return the summary in the response
        return jsonify({'summary': summary})
    except Exception as e:
        # Handle any unexpected errors
        return jsonify({'error': str(e)}), 500

def prepare_data(data):
    matrix = np.array(data['embedding'].apply(json.dumps).apply(literal_eval).to_list())
    tsne = TSNE(n_components=2, perplexity=15, random_state=42, init='random', learning_rate=200)
    vis_dims = tsne.fit_transform(matrix)

    # Preparing the response data
    response_data = []
    for idx, (x_coord, y_coord) in enumerate(vis_dims):
        response_data.append({
            "x": float(x_coord),  # Convert to native Python float
            "y": float(y_coord),  
            "zScore": float(data['z_scores'][idx][-1]),  
            "category": data['_category'][idx]
        })

    return response_data

@app.route('/visualise', methods=['GET'])
def visualise():
    response_data = prepare_data(df)
    return response_data

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
