import pickle, random, pytablewriter
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import precision_recall_curve, auc, f1_score
from sklearn.model_selection import KFold, train_test_split
from main import train_and_test_step, aggregate_and_pickle, train_and_test_with, test_and_train_bots
from utils import get_feature_labels, get_binetflow_files, get_saved_data, mask_features, get_classifier, \
    get_feature_order, exist_summarized_data
from binet_keras import keras_train_and_test


windows = [.15]  # , 1, 2, 5]
binet_files = get_binetflow_files()


def run_files(file_name, window, v2=False):
    print('aggregating {} for {}s v2: {}'.format(file_name, window, v2))

    if not exist_summarized_data(window, file_name, v2):
        if v2:
            aggregate_and_pickle(window, file_name, None, True)
        else:
            aggregate_and_pickle(window, file_name, None, False)


def get_balance():
    for binet in binet_files:
        summary = get_saved_data(0.15, binet)
        _, label = get_feature_labels(summary)
        attacks = sum(label)
        nonattacks = len(label) - attacks
        print("{} | {} ".format(attacks, nonattacks))


def window_shift(window):
    writer = pytablewriter.MarkdownTableWriter()
    writer.table_name = 'Window Shift f1 for {}s'.format(window)
    writer.header_list = ['File', 'Decision Tree', 'Random Forest']
    value_matrix = []
    for file_name in binet_files:
        values = []
        feature, label = get_feature_labels(get_saved_data(window, file_name))
        feature = mask_features(feature)
        values += [file_name, '{0:.4f}'.format(train_and_test_step(feature, label, 'dt', 1000)),
                   '{0:.4f}'.format(train_and_test_step(feature, label, 'rf', 1000))]
        values.append('{0:.4f}'.format(train_and_test_step(feature, label, 'tf', 1000)))
        value_matrix.append(values)
    writer.value_matrix = value_matrix
    writer.write_table()


def file_stats():
    mls = ['dt', 'rf']  # , 'svm', 'nb']
    for window in windows:
        writer = pytablewriter.MarkdownTableWriter()
        writer.table_name = 'File f1 for {}s'.format(window)
        writer.header_list = ['File', 'Decision Tree', 'Random Forest', 'Tensorflow']
        value_matrix = []
        for name in binet_files:
            values = [name]
            feature, label = get_feature_labels(get_saved_data(window, name, v2=True), v2=True)
            # feature = mask_features(feature)
            feat_train, feat_test, label_train, label_test = train_test_split(
                feature, label, test_size=0.3, random_state=42)
            for ml in mls:
                r = train_and_test_with(feat_train, label_train, ml, feat_test, label_test)
                values.append('{0:.4f}, {1:.4f}, {2:.4f}'.format(r['f1'], r['precision'], r['recall']))
                print(values)
            correctness, precision, recall = \
                keras_train_and_test(feat_train, label_train, feat_test, label_test, dimension=22)
            values.append('{0:.4f}, {1:.4f}, {2:.4f}'.format(correctness, precision, recall))
            print(values)
            value_matrix.append(values)

        writer.value_matrix = value_matrix
        writer.write_table()


def kfold_test():
    mls = ['dt', 'rf']
    for window in windows:
        writer = pytablewriter.MarkdownTableWriter()
        writer.table_name = 'KFold validation'
        writer.header_list = ['File', 'Decision Tree', 'Random Forest',
                              'Tensorflow']
        value_matrix = []
        for name in binet_files:
            values = [name]
            feature, label = get_feature_labels(get_saved_data(window, name))
            feature = feature[:int(len(feature) * 10)]
            label = feature[:int(len(label) * 10)]
            kf = KFold(n_splits=10)

            # feature = mask_features(feature)
            for ml in mls:
                scores = []
                pr_scores = []
                for train, test in kf.split(feature):
                    clf = get_classifier(ml)
                    xtrain, ytrain = feature[train], label[train]
                    xtest, ytest = feature[test], label[test]
                    clf.fit(xtrain, ytrain)
                    test_predicts = clf.predict(xtest)
                    test_score = f1_score(ytest, test_predicts)

                    scores.append(test_score)
                    proba = clf.predict_proba(xtest)

                    precision, recall, pr_thresholds = precision_recall_curve(
                        ytest, proba[:, 1])
                    pr_scores.append(auc(recall, precision))
                values.append('{0:.4f}, {1:.4f}, {2:.4f}, {3:.4f}'.format(
                    np.mean(scores), np.std(scores),
                    np.mean(pr_scores), np.std(pr_scores)))
            kf = KFold(n_splits=10)
            f1 = []  # , precision, recall = [], [], []
            for train_index, test_index in kf.split(feature):
                x_train, x_test = feature[train_index], feature[test_index]
                y_train, y_test = label[train_index], label[test_index]
                c, p, r = keras_train_and_test(x_train, y_train, x_test, y_test, dimension=17)
                f1.append(c)
                # precision.append(p)
                # recall.append(r)
            values.append('{0:.4f}, {1:.4f}'.format(np.mean(f1), np.std(f1)))
            value_matrix.append(values)
        writer.value_matrix = value_matrix
        writer.write_table()


def bots_test():
    mls = ['dt', 'rf']
    order = get_feature_order()
    bots = {
        'Neris': [1, 2, 9],
        'Rbot': [3, 4, 10, 11],
        'Virut': [5, 13],
        'Menti': [6],
        'Sogou': [7],
        'Murlo': [8],
        'NSIS.ay': [12]
    }
    bot = ['Neris', 'Rbot', 'Virut', 'Menti', 'Sogou', 'Murlo', 'NSIS.ay']
    bot_data = [0 for _ in binet_files]
    for key, value in bots.items():
        for v in value:
            bot_data[v-1] = bot.index(key)
    for window in windows:
        writer = pytablewriter.MarkdownTableWriter()
        writer.table_name = 'Bot f1 for {}s'.format(window)
        writer.header_list = ['Bot', 'Descision Tree', 'Random Forest', 'Tensorflow']
        value_matrix = []
        features = []
        labels = []

        with open('bot_features', 'rb') as f:
            features = pickle.load(f)
        with open('bot_labels.pk1', 'rb') as f:
            labels = pickle.load(f)
        values = [bot]
        for ml in mls:
            r = test_and_train_bots(features, labels, ml)
            values.append('{0:.4f}, {1:.4f}, {2:.4f}'.format(r['f1'], r['precision'], r['recall']))
        correctness, precision, recall = keras_train_and_test(features, labels, out=8)
        values.append('{0:.4f}, {1:.4f}, {2:.4f}\n'.format(correctness, precision, recall))
        value_matrix.append(values)
        writer.value_matrix = value_matrix
        writer.write_table()


def stats_on_best():
    best = [8, 9, 12]
    summaries = []
    for b in best:
        summaries += get_saved_data(0.15, binet_files[b])
    feature, label = get_feature_labels(summaries)
    scores = []
    for i in range(1, 5):
        feature = [[random.randrange(-(i*10), i*10) for f in feat] for feat in feature]
        f1, _, _ = keras_train_and_test(feature, label)
        scores.append(f1)
    print(scores)


def shuffle_data_test():
    binet = binet_files[-1]
    feature, label = get_feature_labels(get_saved_data(0.15, binet))
    scores = []
    precs = []
    rec = []

    # do normal scoring
    # TODO: do same analysis with dt and rf
    f1, p, r = keras_train_and_test(feature, label)
    scores.append(f1)
    precs.append(p)
    rec.append(r)
    mstd = list(get_mean_std(feature))
    for i in range(1, 5):
        indices = [random.randrange(len(feature)) for _ in range(
            int(len(feature) * ((i*10)/100)))]
        f = feature[:]
        for index in indices:
            f[index] = [np.random.normal(*mstd[i]) for i in range(len(f[index]))]
        f1, p, r = keras_train_and_test(f, label)
        scores.append(f1)
        precs.append(p)
        rec.append(r)

    plt.figure()
    plt.plot(scores, color='lightblue', label='f1')
    plt.plot(precs, color='red', label='precision')
    plt.plot(rec, color='green', label='recall')
    plt.ylabel("Score")
    plt.xlabel("\% of features randomized")
    plt.title("Score randomizing")
    plt.legend(loc='best')
    plt.show()


def get_mean_std(features):
    return zip(np.mean(features, axis=0), np.std(features, axis=0))


def feature_plotting():
    feature, label = get_feature_labels(get_saved_data(0.15, binet_files[12]))
    plt.figure()
    zeroes = set(zip(range(len(feature)), feature[:, 9]))
    ones = set(z for z in zeroes if label[z[0]] == 1)
    del label
    del feature
    zeroes = zeroes.difference(ones)
    plt.scatter(*zip(*zeroes), s=1, c='gray')
    del zeroes
    plt.scatter(*zip(*ones), s=10, c='red')
    plt.show()


def feature_plotting(binet_file):
    feature, label = get_feature_labels(get_saved_data(0.15, binet_file))
    plt.figure()
    rng = range(len(feature))
    zp = zip(rng, feature[:, 9])
    del feature

    zeroes = set(zp)
    ones = set(z for z in zeroes if label[z[0]] == 1)
    zeroes = zeroes.difference(ones)
    del label

    plt.scatter(*zip(*zeroes), s=1, c='gray')
    del zeroes

    plt.scatter(*zip(*ones), s=10, c='red')
    del ones

    plt.show()


if __name__ == '__main__':
    file_path = '/media/thiago/ubuntu/datasets/network/stratosphere_botnet_2011/ctu_13/raw/capture20110818-2.binetflow'
    feature_plotting(file_path)
    # v2 = False
    # Parallel(n_jobs=3)(delayed(run_files)(name, 1, v2) for name in binet_files)
    # Parallel(n_jobs=2)(delayed(window_shift)(i) for i in windows)
    # window_shift(0.15)
    # print('For tuned down features of size 12')
    # print("70/30 split")
    # file_stats()
    # get_balance()
    # stats_on_best()
    # window_shift(.15)
    # kfold_test()
    # shuffle_data_test()
    # feature_plotting()
    pass
