- [yamlett - Yet Another Machine Learning Experiment Tracking Tool](#orgbddaa9c)
  - [Set up the experiment](#org68b8f36)
  - [MLflow-like tracking](#orgc32df43)
  - [`yamlett`-like tracking](#org72c2dcd)
- [Roadmap <code>[2/9]</code>](#org72fd744)



<a id="orgbddaa9c"></a>

# yamlett - Yet Another Machine Learning Experiment Tracking Tool

`yamlett` provides a simple but flexible way to track your ML experiments.

It has a simple interface with only two primitives: `Experiment` and `Run`.

-   An `Experiment` is a named collection of `Run` objects. It is a wrapper around a `pymongo.collection.Collection` object ([reference](https://pymongo.readthedocs.io/en/stable/api/pymongo/collection.html#pymongo.collection.Collection)), meaning that you can query it using `find` or `aggregate`. Think of it as a way to collect all the modeling iterations of a specific project.
-   A `Run` is used to store information about one iteration of your `Experiment`. You can use it to record any ([BSON](http://bsonspec.org)-serializable) information you want such as model parameters, metrics, or pickled artifacts.

The main difference with other tracking tools (e.g. MLflow) is that you can save complex information using dictionaries or lists and filter on them later using MongoDB queries. This is helpful to save run information using whatever structure you prefer. For a quick example, let&rsquo;s compare a simple model run using a tracking approach similar to MLflow and the preferred tracking approach with `yamlett`.


<a id="org68b8f36"></a>

## Set up the experiment

Let&rsquo;s first load a dataset for a simple classification problem that ships with scikit-learn.

```python
%load_ext autoreload
%autoreload 2
from sklearn.datasets import load_iris

X, y = load_iris(return_X_y=True)
```

Let&rsquo;s also create a simple logistic regression model and simply train that model on our simple dataset, increasing the number of iterations and changing the regularization strength.

```python
from sklearn.linear_model import LogisticRegression

model = LogisticRegression(max_iter=200, C=0.1)
model.fit(X, y)
```


<a id="orgc32df43"></a>

## MLflow-like tracking

With `yamlett`, you are free to organize you tracking information so you could decide to store it using a &ldquo;flat&rdquo; approach similar to MLflow where each key has an associated value and there is no nesting involved.

```python
from yamlett import Run
from sklearn.metrics import f1_score
from collections import Counter

run = Run()

# store some information about your trained model: its class and its parameters
run.store("params_model_class", model.__class__.__name__)
for param_name, param_value in model.get_params().items():
    run.store(f"params_model_{param_name}", param_value)

# store information about your data
run.store("data_n_features", X.shape[0])
run.store("data_n_observations", X.shape[1])

# store the F1 score on the train data
run.store("metrics_train_f1_score", f1_score(y, model.predict(X), average="weighted"))

# you could even store a pickled version of your model
# run.store("model", pickle.dumps(model))
```

After running this code, we can retrieve the stored information by calling `run.data`:

    {'_id': '901c6823493d429cae4ddb84c91a7768',
     '_yamlett': {'created_at': datetime.datetime(2020, 12, 5, 21, 36, 14, 17000),
                  'last_modified_at': datetime.datetime(2020, 12, 5, 21, 36, 14, 461000)},
     'data_n_features': 150,
     'data_n_observations': 4,
     'metrics_train_f1_score': 0.9599839935974389,
     'params_model_C': 0.1,
     'params_model_class': 'LogisticRegression',
     'params_model_class_weight': None,
     'params_model_dual': False,
     'params_model_fit_intercept': True,
     'params_model_intercept_scaling': 1,
     'params_model_l1_ratio': None,
     'params_model_max_iter': 200,
     'params_model_multi_class': 'auto',
     'params_model_n_jobs': None,
     'params_model_penalty': 'l2',
     'params_model_random_state': None,
     'params_model_solver': 'lbfgs',
     'params_model_tol': 0.0001,
     'params_model_verbose': 0,
     'params_model_warm_start': False}

This approach is straightforward: one scalar for each key in the document. However, one downside of this approach is that you need to maintain your own namespace convention. For example here, we used underscores to separate the different levels of information (params, data, metrics, etc) but this can quickly get confusing if chosen incorrectly: is it `params/model/fit_intercept` or `params/model_fit/intercept` ? It&rsquo;s also more work than needed when information already comes nicely organized (e.g. `model.get_params()`).


<a id="org72c2dcd"></a>

## `yamlett`-like tracking

The method we propose in this package is to leverage Python dictionaries / NoSQL DB documents to automatically store your information in a structured way. Let&rsquo;s see what it looks like using a similar run as the example above:

```python
from yamlett import Run

run = Run()

# store your model information
model_info = {
    "class": model.__class__.__name__,
    **model.get_params(),
}
run.store(f"model.metadata", model_info)

# store information about your data
run.store("data", {"n_features": X.shape[0], "n_observations": X.shape[1]})

# store the F1 score on your train data
run.store("metrics.f1_score", f1_score(y, model.predict(X), average="weighted"))

# you could even store a pickled version of your model
# run.store("model.artifact", pickle.dumps(model))
```

Once again, let&rsquo;s call `run.data` and see what information we stored:

    {'_id': '8cdbabae6c4441f9bf9aae02f09033f9',
     '_yamlett': {'created_at': datetime.datetime(2020, 12, 5, 21, 35, 11, 542000),
                  'last_modified_at': datetime.datetime(2020, 12, 5, 21, 35, 11, 621000)},
     'data': {'n_features': 150, 'n_observations': 4},
     'metrics': {'f1_score': 0.9599839935974389},
     'model': {'metadata': {'C': 0.1,
                            'class': 'LogisticRegression',
                            'class_weight': None,
                            'dual': False,
                            'fit_intercept': True,
                            'intercept_scaling': 1,
                            'l1_ratio': None,
                            'max_iter': 200,
                            'multi_class': 'auto',
                            'n_jobs': None,
                            'penalty': 'l2',
                            'random_state': None,
                            'solver': 'lbfgs',
                            'tol': 0.0001,
                            'verbose': 0,
                            'warm_start': False}}}

The run information is now stored in a document that can be easily parsed based on its structure. Additionally, because `yamlett` is built on top of MongoDB, you can query runs in an `Experiment` using `find` or `aggregate`. For instance, we could retrieve all runs in the default experiment for which:

1.  the model was fit with bias term
2.  on a dataset with at least 3000 data points
3.  that yielded an F1 score of at least 0.9

```python
from yamlett import Experiment

e = Experiment()

e.find(
    {
        "params.model.fit_intercept": True,
        "data.n_observations": {"$gte": 3000},
        "metrics.f1_score": {"$gte": 0.9},
    }
)
```

Note that `yamlett` does not enforce the document hierarchy so you are free to organize your run data as you see fit. Finally, we find `yamlett` particularly useful if your experiments are configuration-driven. For instance, if you can load your configuration file as a dictionary, then you can easily save it in along with other information using `run.store("config", config")`.


<a id="org72fd744"></a>

# Roadmap <code>[2/9]</code>

-   [X] Add basic unit tests
-   [X] Add tests across python version using tox
    -   tox replaced by Github Actions
-   [ ] Add CI/CD
-   [ ] Release 0.1.0 to github
-   [ ] Release to pypi
-   [ ] Add e2e runnable example
-   [ ] Add example for connecting to Metabase and Presto
    -   metabase allows connecting to an instance of mongodb and query data
    -   sql is more common so we can plug presto on top of mongodb and link metabase to presto
    -   caveat that the schema cannot change when using Presto: ie no new fields in new runs
-   [ ] Use environment variables to define MongoDB parameters
-   [ ] Enable artifacts to be stored on disk or in cloud storage
    -   Let users provide an object that supports `open`, `write`, and `read` and interacts with the file system
