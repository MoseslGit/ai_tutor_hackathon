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


def main():
    parser = argparse.ArgumentParser(description='Process a CSV file.')
    parser.add_argument('--csv_file', type=str, help='Path to the CSV file')
    parser.add_argument('--demo', action='store_true', help='Run the demo')

    args = parser.parse_args()
    if args.demo:
        print('Running the demo')
        # generate a random embeddings matrix and z score matrix
        embeddings = np.random.randn(100, 400)
        current_z_scores = np.random.randn(100, 1)
        no_unasked_qs = 40
        indices = np.random.choice(range(100), no_unasked_qs, replace=False)

        # assign a random subset of current z scores to np.nan
        current_z_scores[indices] = np.nan

        # compute Q score for each question
        Q_scores = []
        for i in range(100):
            cosine_similarities_i = []
            z_scores_i = []
            # compute the cosine distance between embedding i and all others
            for j in range(100):
                if j == i or np.isnan(current_z_scores[j]):
                    continue
                d_i_j = cosine_distance(embeddings[i], embeddings[j])
                z_scores_i.append(current_z_scores[j]) 
                cosine_similarities_i.append(d_i_j)
            
            cosine_similarities_i = np.array(cosine_similarities_i)
            z_scores_i = np.array(z_scores_i)

            # standardise the similarities
            normalised_cosine_similarities_i = (cosine_similarities_i - np.mean(cosine_similarities_i)) / np.std(cosine_similarities_i)

            # compute the q score
            Q_i = np.sum(normalised_cosine_similarities_i/np.sum(normalised_cosine_similarities_i) * z_scores_i)
            Q_scores.append(Q_i)
        plt.hist(Q_scores)
        plt.show()

    else:
        # Read the CSV file
        df = pd.read_csv(args.csv_file)

        # Read the embeddings matrix

        # Read the z score matrix


if __name__ == '__main__':
    main()

