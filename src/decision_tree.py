import sys
import os
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.externals import joblib
from sklearn import tree
sys.path.append(os.path.join('..', 'src'))
sys.path.append(os.path.join('src'))
import evaluation


def load_data():
    filename = "splitter/train.csv"
    print("Loading data from {}".format(filename))
    train = pd.read_csv(filename)

    filename = 'splitter/validation.csv'
    print("Loading data from {}".format(filename))
    validate = pd.read_csv(filename)

    return train, validate


def join_tables(train, validate):
    print("Joining tables for consistent encoding")
    return train.append(validate).drop('date', axis=1)


def encode_categorical_columns(df):
    obj_df = df.select_dtypes(include=['object', 'bool']).copy().fillna('-1')
    lb = LabelEncoder()
    for col in obj_df.columns:
        df[col] = lb.fit_transform(obj_df[col])
    return df


def encode(train, validate):
    print("Encoding categorical variables")
    train_ids = train.id
    validate_ids = validate.id

    joined = join_tables(train, validate)

    encoded = encode_categorical_columns(joined.fillna(-1))

    print("Not predicting returns...")
    encoded.loc[encoded.unit_sales < 0, 'unit_sales'] = 0

    validate = encoded[encoded['id'].isin(validate_ids)]
    train = encoded[encoded['id'].isin(train_ids)]
    return train, validate


def make_model(train):
    print("Creating decision tree model")
    train_dropped = train.drop('unit_sales', axis=1)
    target = train['unit_sales']

    clf = tree.DecisionTreeRegressor()
    clf = clf.fit(train_dropped, target)
    return clf


def overwrite_unseen_prediction_with_zero(preds, train, validate):
    cols_item_store = ['item_nbr', 'store_nbr']
    cols_to_use = validate.columns.drop('unit_sales') if 'unit_sales' in validate.columns else validate.columns
    validate_train_joined = pd.merge(validate[cols_to_use], train, on=cols_item_store, how='left')
    unseen = validate_train_joined[validate_train_joined['unit_sales'].isnull()]
    validate['preds'] = preds
    validate.loc[validate.id.isin(unseen['id_x']), 'preds'] = 0
    preds = validate['preds'].tolist()
    return preds


def make_predictions(clf, validate):
    print("Making prediction on validation data")
    validate_dropped = validate.drop('unit_sales', axis=1).fillna(-1)
    validate_preds = clf.predict(validate_dropped)
    return validate_preds


def write_predictions_and_score(validation_score, model, columns_used):
    key = "decision_tree"
    if not os.path.exists(key):
        os.makedirs(key)
    filename = './{}/model.pkl'.format(key)
    print("Writing to {}".format(filename))
    joblib.dump(model, filename)

    filename = './{}/score_and_metadata.csv'.format(key)
    print("Writing to {}".format(filename))
    score = pd.DataFrame({'estimate': [validation_score], 'columns_used': [columns_used]})
    score.to_csv(filename, index=False)

    print("Done deciding with trees")


def main():
    original_train, original_validate = load_data()
    train, validate = encode(original_train, original_validate)
    model = make_model(train)
    validation_predictions = make_predictions(model, validate)

    print("Calculating estimated error")
    validation_score = evaluation.nwrmsle(validation_predictions, validate['unit_sales'], validate['perishable'])

    write_predictions_and_score(validation_score, model, original_train.columns)

    print("Decision tree analysis done with a validation score (error rate) of {}.".format(validation_score))


if __name__ == "__main__":
    main()
