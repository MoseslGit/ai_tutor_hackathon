import numpy as np
import pandas as pd
import random
from sklearn.preprocessing import MinMaxScaler
from fsrs_optimizer import lineToTensor, FSRS
import torch
from tqdm.auto import tqdm
import matplotlib.pyplot as plt


import numpy as np
import pandas as pd
import random
from sklearn.preprocessing import MinMaxScaler
from fsrs_optimizer import lineToTensor, FSRS
import torch
from tqdm.auto import tqdm
import matplotlib.pyplot as plt
# Necessary Input:
# z_score - only for questions that have been asked
# asked questions to put into scheduler

# parameters for FSRS
w = [1.1008, 1.2746, 5.7619, 10.5114, 5.3148, 1.5796, 1.244, 0.003, 1.5741, 0.1741, 1.0137, 2.7279, 0.0114, 0.3071, 0.3981, 0.0, 1.9569]
requestRetention = 0.82  # recommended setting: 0.8 ~ 0.9

# parameters for Anki
graduatingInterval = 1
easyInterval = 4
easyBonus = 1.3
hardInterval = 1.2
intervalModifier = 1
newInterval = 0
minimumInterval = 1
leechThreshold = 8
leechSuspend = False

# common parameters
maximumInterval = 36500
new_cards_limits = 20
review_limits = 400
max_time_limts = 10000
learn_days = 50

# smooth curves
moving_average_period = 14

# Set it to True if you don't want the optimizer to use the review logs from suspended cards.
filter_out_suspended_cards = False

# Red: 1, Orange: 2, Green: 3, Blue: 4, Pink: 5, Turquoise: 6, Purple: 7
# Set it to [1, 2] if you don't want the optimizer to use the review logs from cards with red or orange flag.
filter_out_flags = []
    

def get_schedule_scores(df, lesson_id):
    '''Gets a df that contains id of question and schedule_scores for each one.
    Input takes the full df and the lesson_id, or the number of days since the beginning of the course.
    FSRS uses a calculated stability metric, which is how "stable" the idea is in your mind,
    and schedules the next occurence of the card. We then scale this and normalize to give an output number
    showing how urgent the card is, with 1 being the most urgent.
    This is simply a time-series model with Markov property:
    Depending on half-life, recall probability, result of recall, and difficulty, we define
    a memory state-transition equation to update at every step.
    We combine this with a Stochastic Shortest Path problem - the number of reviews required for memorizing something
    to the require half-life is uncertain, so we combine the SSP and MMC to
    find the optimal review time over iterations.'''
    deck_size = len(df)
    def calculate_review_duration(states, times):
        if states[-1] != 2:
            return 5
        else:
            # Find the most recent transition to state 2 from either 1 or 3
            for i in range(len(states) - 1, 0, -1):
                if states[i] == 2 and (states[i - 1] == 1 or states[i - 1] == 3):
                    return times[i] - times[i - 1]
            return 5  # Default value if no valid transition is found

    # Apply the function to each row
    df['review_duration'] = [calculate_review_duration(s, t) for s, t in zip(df['review_state'], df['review_time'])]

    # Define the bins for the intervals
    # bins = [0.25, 0.5, 0.75]
    # df['z_score_last'] = df['z_scores'].apply(lambda x: x[-1] if isinstance(x, list) and x else np.nan)
    # # Use numpy's digitize method to convert z_scores to review_rating
    # df['review_rating'] = np.digitize(df['z_score_last'], bins) + 1
    # df['review_rating'] = 5 - df['review_rating']

    def assign_rating(row):
        # Extract the last z_score value
        z_score = row['z_scores'][-1] if isinstance(row['z_scores'], list) and row['z_scores'] else None
        
        # Assign ratings based on z_score
        if z_score is not None:
            if z_score <= 0.25:
                return 1
            elif z_score <= 0.5:
                return 2
            elif z_score <= 0.75:
                return 3
            else:
                return 4
        else:
            return None  # or some default value
    df['review_rating'] = df.apply(assign_rating, axis=1) 
    df['review_time_curr'] = df['review_time'].apply(lambda x: x[-1])
    df['review_state_curr'] = df['review_state'].apply(lambda x: x[-1])
    New = 0
    Learning = 1
    Review = 2
    Relearning = 3

    df.sort_values(by=["id", "review_time_curr"], inplace=True, ignore_index=True)


    recall_card_revlog = df[
        (df["review_state_curr"] == Review) & (df["review_rating"].isin([2, 3, 4]))
    ]
    review_rating_prob = np.zeros(3)
    review_rating_prob[recall_card_revlog["review_rating"].value_counts().index - 2] = (
        recall_card_revlog["review_rating"].value_counts()
        / recall_card_revlog["review_rating"].count()
    )
    random_array = np.random.rand(4)
    random_array /= random_array.sum()
    first_rating_prob = random_array


    df["review_state_curr"] = df["review_state_curr"].map(
        lambda x: x if x != New else Learning)

    recall_costs = np.zeros(3)
    recall_costs_df = recall_card_revlog.groupby(by="review_rating")[
        "review_duration"
    ].mean()
    recall_costs[recall_costs_df.index - 2] = recall_costs_df / 1000

    state_sequence = np.array(df["review_state_curr"])
    duration_sequence = np.array(df["review_duration"])
    learn_cost = round(
        df[df["review_state_curr"] == Learning]["review_duration"].sum()
        / len(df["id"].unique())
        / 1000,
        1,
    )

    state_block = dict()
    state_count = dict()
    state_duration = dict()
    last_state = state_sequence[0]
    state_block[last_state] = 1
    state_count[last_state] = 1
    state_duration[last_state] = duration_sequence[0]
    for i, state in enumerate(state_sequence[1:]):
        state_count[state] = state_count.setdefault(state, 0) + 1
        state_duration[state] = state_duration.setdefault(
            state, 0) + duration_sequence[i]
        if state != last_state:
            state_block[state] = state_block.setdefault(state, 0) + 1
        last_state = state

    recall_cost = round(state_duration[Review] / state_count[Review] / 1000, 1)

    if Relearning in state_count and Relearning in state_block:
        forget_cost = round(
            state_duration[Relearning] /
            state_block[Relearning] / 1000 + recall_cost,
            1,
        )

    def generate_rating(review_type):
        if review_type == "new":
            return np.random.choice([1, 2, 3, 4], p=first_rating_prob)
        elif review_type == "recall":
            return np.random.choice([2, 3, 4], p=review_rating_prob)

    class Collection:
        def __init__(self):
            self.model = FSRS(w)
            self.model.eval()

        def states(self, t_history, r_history):
            with torch.no_grad():
                line_tensor = lineToTensor(
                    list(zip([str(t_history)], [str(r_history)]))[0]
                ).unsqueeze(1)
                output_t = self.model(line_tensor)
                return output_t[-1][0]

        def next_states(self, states, t, r):
            with torch.no_grad():
                return self.model.step(torch.FloatTensor([[t, r]]), states.unsqueeze(0))[0]

        def init(self, idx):
            t = df["review_time_curr"][idx]
            r = df["review_rating"][idx]
            p = round(first_rating_prob[r - 1], 2)
            new_states = self.states(t, r)
            return r, t, p, new_states


    feature_list = [
        "id",
        "difficulty",
        "stability",
        "retrievability",
        "delta_t",
        "reps",
        "lapses",
        "last_date",
        "due",
        "r_history",
        "t_history",
        "p_history",
        "states",
        "time",
        "factor",
    ]
    field_map = {key: i for i, key in enumerate(feature_list)}


    def fsrs4anki_scheduler(stability):
        def constrain_interval(stability):
            if stability > 0:
                return min(
                    max(1, round(9 * stability * (1 / requestRetention - 1))),
                    maximumInterval,
                )
            else:
                return 1

        interval = constrain_interval(stability)
        return interval


    def scheduler(fsrs_inputs):
            return fsrs4anki_scheduler(fsrs_inputs), 2.5

    #for scheduler_name in ("anki", "fsrs"):
    for scheduler_name in ["fsrs"]:
        new_card_per_day = np.array([0] * learn_days)
        new_card_per_day_average_per_period = np.array([0.0] * learn_days)
        review_card_per_day = np.array([0.0] * learn_days)
        review_card_per_day_average_per_period = np.array([0.0] * learn_days)
        time_per_day = np.array([0.0] * learn_days)
        time_per_day_average_per_period = np.array([0.0] * learn_days)
        learned_per_day = np.array([0.0] * learn_days)
        retention_per_day = np.array([0.0] * learn_days)
        expected_memorization_per_day = np.array([0.0] * learn_days)

        card = pd.DataFrame(
            np.zeros((deck_size, len(feature_list))),
            index=range(deck_size),
            columns=feature_list,
        )
        card["id"] = df["id"]
        card["states"] = card["states"].astype(object)
        card['reps'] = df['review_state'].apply(lambda x: len(x))
        card["lapses"] = 0
        card["due"] = learn_days
        card["last_date"] = df["review_time"].apply(lambda x: x[-1])
        
        student = Collection()
        random.seed(2022)
        # do 1 step:
        day = lesson_id
        reviewed = 0
        learned = 0
        review_time_today = 0
        learn_time_today = 0

        card["delta_t"] = day - card["last_date"]
        card["retrievability"] = np.power(
            1 + card["delta_t"] / (9 * card["stability"]), -1
        )
        need_learn = card[card["stability"] == 0]

        for idx in need_learn.index:
            if (
                learned >= new_cards_limits
                or review_time_today + learn_time_today >= max_time_limts
            ):
                break
            learned += 1
            learn_time_today += learn_cost
            #card.iat[idx, field_map["last_date"]] = day

            #card.iat[idx, field_map["reps"]] = 1
            #card.iat[idx, field_map["lapses"]] = 0

            r, t, p, new_states = student.init(idx)
            new_stability = float(new_states[0])
            new_difficulty = float(new_states[1])
            card['r_history'] = card['r_history'].astype(object)
            card['t_history'] = card['t_history'].astype(object)
            card['p_history'] = card['p_history'].astype(object)
            card.iat[idx, field_map["r_history"]] = str(r)
            card.iat[idx, field_map["t_history"]] = str(t)
            card.iat[idx, field_map["p_history"]] = str(p)
            card.iat[idx, field_map["stability"]] = new_stability
            card.iat[idx, field_map["difficulty"]] = new_difficulty
            card.iat[idx, field_map["states"]] = new_states

            delta_t, factor = scheduler(new_stability)
            card.iat[idx, field_map["due"]] = day + delta_t
            #card.iat[idx, field_map["due"]] = day + delta_t
            card.iat[idx, field_map["factor"]] = factor

            card.iat[idx, field_map["time"]] = learn_cost


        new_card_per_day[day] = learned
        review_card_per_day[day] = reviewed
        learned_per_day[day] = learned_per_day[day - 1] + learned
        time_per_day[day] = review_time_today + learn_time_today
        expected_memorization_per_day[day] = sum(
            card[card["retrievability"] > 0]["retrievability"]
        )

        if day >= moving_average_period:
            new_card_per_day_average_per_period[day] = np.true_divide(
                new_card_per_day[day - moving_average_period: day].sum(),
                moving_average_period,
            )
            review_card_per_day_average_per_period[day] = np.true_divide(
                review_card_per_day[day - moving_average_period: day].sum(),
                moving_average_period,
            )
            time_per_day_average_per_period[day] = np.true_divide(
                time_per_day[day - moving_average_period: day].sum(),
                moving_average_period,
            )
        else:
            new_card_per_day_average_per_period[day] = np.true_divide(
                new_card_per_day[: day + 1].sum(), day + 1
            )
            review_card_per_day_average_per_period[day] = np.true_divide(
                review_card_per_day[: day + 1].sum(), day + 1
            )
            time_per_day_average_per_period[day] = np.true_divide(
                time_per_day[: day + 1].sum(), day + 1
            )
    scaler = MinMaxScaler(feature_range=(0, 1))
    card['schedule_score'] = scaler.fit_transform(card[['due']])

    # Inverting the values so that lower 'due' values are closer to 1
    card['schedule_score'] = 1 - card['schedule_score']

    # Returning the DataFrame with 'id' and 'schedule_score'
    result = card[['id', 'schedule_score']]
    return result

def cosine_distance(a, b):
    cosine_similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return 1 - cosine_similarity

def compute_Q_scores(embeddings, current_z_scores):
    
    # compute Q score for each question
        Q_scores = []
        # compute the cosine distance between embedding i and all others
        inv_cosine_similarities = np.zeros((embeddings.shape[0],embeddings.shape[0]))
        for i in range(embeddings.shape[0]):
            # TODO: Make this loop more efficient
            for j in range(0,embeddings.shape[0]):
                if j == i or np.isnan(current_z_scores[j]):
                    inv_cosine_similarities[i,j] = np.nan
                else:
                    d_i_j = cosine_distance(embeddings[i], embeddings[j])
                    inv_cosine_similarities[i,j] = 1/d_i_j
                    inv_cosine_similarities[j,i] = 1/d_i_j

        # normalise inv_cosine_similarities
        max_val = np.nanmax(inv_cosine_similarities)
        min_val = np.nanmin(inv_cosine_similarities)

        normalised_inv_cosine_similarities = (inv_cosine_similarities - min_val)/(max_val - min_val)
        total_normalised_inv_cosine_similarities = np.nansum(normalised_inv_cosine_similarities)/2
        for i in range(embeddings.shape[0]):
            # compute Q score for question i
            Q_score_i = 0
            for j in range(embeddings.shape[0]):
                if j != i and not np.isnan(current_z_scores[j]):
                    Q_score_i += normalised_inv_cosine_similarities[i,j]/(total_normalised_inv_cosine_similarities) * current_z_scores[j]
            Q_scores.append(Q_score_i)

        # normalise Q scores
        max_val = np.nanmax(Q_scores)
        min_val = np.nanmin(Q_scores)
        Q_scores = (Q_scores - min_val)/(max_val - min_val)
        
        return Q_scores


def calc_z_score(question, answer, response, response_time, is_fact):
    """
    Calculate the z-score for a given question and response.

    Idea is that if fact based the logic is binary - either you know the answer or you don't.
    If you know set a low z score of 0.1 - answer memorised
    If you don't know set a neutral z score of 0.5 - answer guessed

    If reasoning based, the z score is calculated based on proportion of time spent thinking about the question out of total time taken to answer.
    regardless of true or false. Idea is that if it takes a long time to answer, even if you are correct it was hard for you.


    Over several askings of a question should trigger the memorisation loop where 

    Parameters:
    question (str): The question asked.
    answer (str): The correct answer to the question.
    response (str): The response given by the student.
    response_time (float): The time taken by the student to respond in seconds.
    is_fact (bool): Fact based True or False.

    Returns:
    float: The z-score calculated based on the response time.
    """
    # count number of words in question and adjust response time
    question_length = len(question.split())

    # use an avg reading rate of 200 words per minute
    reading_time = 60 * (question_length / 200)
    understanding_time = response_time - reading_time
    
    # if negative understanding time, question was answered without much thought - answer known or guessed
    if understanding_time < 0:
        understanding_time = 0
        # if wrong, assume answer was guessed and set a neutral z score
        if response != answer:
            return 0.5
        # if correct, assume answer was memorised and set a z score of 0.1
        if response == answer:
            return 0.1

    # if fact_based question and correct answer, assume answer was known and set a neutral z score
    if is_fact:
        if response == answer:
            # add logic here to think about how many times person has seen this
            # rn will just run this till answer is memorised and prev loop is run so z score is 0.1
            return 0.1
        else:
            return 0.5
    
    else:
        # reasoning based question, calculate z score based on time taken to answer
        # if thinking proportion high - question was challenging, not punished for very long vs slightly long
        return understanding_time/response_time


def calc_z_score(question, answer, response, response_time, is_fact):
    """
    Calculate the z-score for a given question and response.

    Idea is that if fact based the logic is binary - either you know the answer or you don't.
    If you know set a low z score of 0.1 - answer memorised
    If you don't know set a neutral z score of 0.5 - answer guessed

    If reasoning based, the z score is calculated based on proportion of time spent thinking about the question out of total time taken to answer.
    regardless of true or false. Idea is that if it takes a long time to answer, even if you are correct it was hard for you.


    Over several askings of a question should trigger the memorisation loop where 

    Parameters:
    question (str): The question asked.
    answer (str): The correct answer to the question.
    response (str): The response given by the student.
    response_time (float): The time taken by the student to respond in seconds.
    is_fact (bool): Fact based True or False.

    Returns:
    float: The z-score calculated based on the response time.
    """
    # count number of words in question and adjust response time
    question_length = len(question.split())

    # use an avg reading rate of 200 words per minute
    reading_time = 60 * (question_length / 200)
    understanding_time = response_time - reading_time
    
    # if negative understanding time, question was answered without much thought - answer known or guessed
    if understanding_time < 0:
        understanding_time = 0
        # if wrong, assume answer was guessed and set a neutral z score
        if response != answer:
            return 0.5
        # if correct, assume answer was memorised and set a z score of 0.1
        if response == answer:
            return 0.1

    # if fact_based question and correct answer, assume answer was known and set a neutral z score
    if is_fact:
        if response == answer:
            # add logic here to think about how many times person has seen this
            # rn will just run this till answer is memorised and prev loop is run so z score is 0.1
            return 0.1
        else:
            return 0.5
    
    else:
        # reasoning based question, calculate z score based on time taken to answer
        # if thinking proportion high - question was challenging, not punished for very long vs slightly long
        return understanding_time/response_time