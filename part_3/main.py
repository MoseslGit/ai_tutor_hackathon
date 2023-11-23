import pandas as pd
import numpy as np
import argparse
import matplotlib.pyplot as plt
np.random.seed(42)
"""
Script computes Q scores for each question in csv file using embedding matrix and latest column in z score matrix
For each question computes cosine distance of embedding from each other previously answered question (z score not np.nan)
Q_score_i = Sum over j=!i 1/embedding_cosine_dist_i_j * z_score_j 
"""


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

def main():
    parser = argparse.ArgumentParser(description='Process a CSV file.')
    parser.add_argument('--pkl_file', type=str, help='Path to the CSV file')
    parser.add_argument('--demo', action='store_true', help='Run the demo')
    parser.add_argument('--out_pkl_file', type=str, help='Path to the output CSV file')

    args = parser.parse_args()
    if args.demo:
        print('Running the demo')
        # generate a random embeddings matrix and z score matrix
        embeddings = np.random.randn(100, 400)
        current_z_scores = np.random.randn(100)
        no_unasked_qs = 40
        indices = np.random.choice(range(100), no_unasked_qs, replace=False)

        # assign a random subset of current z scores to np.nan
        current_z_scores[indices] = np.nan

        Q_scores = compute_Q_scores(embeddings, current_z_scores)

    else:
        # Read the CSV file
        df = pd.read_pickle(args.pkl_file)
        
        # if no z_scores column generate random z scores between 0 and 1
        if 'z_score' not in df.columns:
            z_scores = np.random.rand(df.shape[0])
            # set a random proportion of z scores to np.nan
            no_unasked_qs = np.random.randint(0, df.shape[0]//2)
            indices = np.random.choice(range(df.shape[0]), no_unasked_qs, replace=False)
            z_scores[indices] = np.nan
            df['z_score'] = z_scores
        
        # Read the embeddings matrix
        embeddings = df['embedding']
    
        # # Read the z score matrix
        # z_score = df['z_score'][:,-1]

        # # Read Q score matrix
        # Q_score_matrix = df['Q_score']

        Q_scores = compute_Q_scores(embeddings, df['z_score'])

        
        # # Append Q scores to Q score matrix column
        # Q_score_matrix = np.append(Q_score_matrix, Q_scores, axis=1)

        # df['Q_score'] = Q_score_matrix

        # # save df as pickle
        # df.to_pickle(args.out_pkl_file)

if __name__ == '__main__':
    main()

