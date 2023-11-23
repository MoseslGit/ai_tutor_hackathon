from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/lessonSummary', methods=['GET'])
def lesson_summary():
    # Extract parameters from request (if needed)
    lesson_id = request.args.get('lessonId', type=int)

    # Normally, here you'd fetch or compute the summary data
    response = {
        "summary": "Lorem ipsum dolor sit amet..."
    }
    return jsonify(response)

@app.route('/question', methods=['GET'])
def get_question():
    # Extract parameters
    lesson_id = request.args.get('lessonId', type=int)
    question_number = request.args.get('questionNumber', type=int)

    # Fetch or compute the question data
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

    # Process the posted data (e.g., record the answer and time taken)
    # For this example, we'll just send back a confirmation
    return jsonify({"message": "Response recorded"})

@app.route('/explain', methods=['GET'])
def explain():
    # Extract parameters
    question_id = request.args.get('questionId', type=int)

    # Fetch or compute the explanation
    response = {
        "explanation": "Lorem ipsum dolor..."
    }
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
