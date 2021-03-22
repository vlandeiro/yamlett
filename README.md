# yamlett - Yet Another Machine Learning Experiment Tracking Tool

1.  [What is `yamlett`?](#what-is-yamlett)
2.  [Installation](#installation)
3.  [Getting started](#orgb8dfc38)
4.  [Examples](#example)
    1.  [MLflow vs yamlett](#org76d90a4)
    2.  [Storing large artifacts](#orga271eb5)

![PyPI](https://img.shields.io/pypi/v/yamlett)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/yamlett)
![PyPI - License](https://img.shields.io/pypi/l/yamlett)


<a id="what-is-yamlett"></a>

## What is `yamlett`?

`yamlett` provides a simple but flexible way to track your ML experiments.

It has a simple interface with only two primitives: `Run` and `Experiment`.

-   A `Run` is used to store information about one iteration of your `Experiment`. You can use it to record any ([BSON](http://bsonspec.org)-serializable) information you want such as model parameters, metrics, or pickled artifacts.
-   An `Experiment` is a collection of `Run` objects. It has a `name` and it is a wrapper around a `pymongo.collection.Collection` object ([reference](https://pymongo.readthedocs.io/en/stable/api/pymongo/collection.html#pymongo.collection.Collection)), meaning that you can query it using `find` or `aggregate`. Think of it as a way to collect all the modeling iterations for a specific project.

The main difference with other tracking tools (e.g. MLflow) is that `yamlett` lets you save complex structured information using dictionaries or lists and filter on them later using MongoDB queries.

`yamlett` is particularly useful if your experiments are configuration-driven. Once your configuration is loaded as a python object, storing it is as easy as `run.store("config", config)`.


<a id="installation"></a>

## Installation

`yamlett` can be installed with `pip`:

```sh
pip install yamlett
```

It also requires a MongoDB instance that you can connect to. If you don't have one and just want to try out `yamlett`, we provide a [docker compose file](docker-compose.yaml) that starts a MongoDB instance available at `localhost:27017` (along with instances of [Presto](https://prestodb.io) and [Metabase](https://www.metabase.com)).


<a id="orgb8dfc38"></a>

## Getting started

In `yamlett`, `MongoClient` [connection parameters](https://pymongo.readthedocs.io/en/stable/api/pymongo/mongo_client.html#pymongo.mongo_client.MongoClient) can be passed as keyword arguments in both `Run` and `Experiment` to specify what MongoDB instance you want to connect to. If you don't pass anything, the default arguments (`localhost:27017`) will be used. If you have a custom MongoDB instance, you can specify its `host` and `port` when creating a `Run` using `run=Run(host="mymongo.host.com", port=27017)`. Once you have a run instantiated, you can store a key/value pair with `run.store(key, value)` and you can look at the stored data with `run.data`.


<a id="example"></a>

## Examples


<a id="org76d90a4"></a>

### MLflow vs yamlett

In this section, we compare the same model run but with two different tracking different approaches: MLflow-like vs yamlett.

1.  Set up the experiment

    First, let's load a dataset for a simple classification problem that ships with scikit-learn.
    
    ```jupyter-python
    from sklearn.datasets import load_iris
    
    X, y = load_iris(return_X_y=True)
    ```
    
    Then, we create a logistic regression model and train that model on the iris dataset, increasing the number of iterations and changing the regularization strength.
    
    ```jupyter-python
    from sklearn.linear_model import LogisticRegression
    
    model = LogisticRegression(max_iter=200, C=0.1)
    model.fit(X, y)
    ```

2.  MLflow-like tracking

    With `yamlett`, you are free to organize you tracking information so you could decide to store it using a "flat" approach similar to MLflow where each key has an associated value and there can be no nesting.
    
    ```jupyter-python
    from yamlett import Run
    from sklearn.metrics import f1_score
    
    run = Run(id="mlflow-like-run")
    
    # store some information about your trained model: its class and its parameters
    run.store("params_model_class", model.__class__.__name__)
    for param_name, param_value in model.get_params().items():
        run.store(f"params_model_{param_name}", param_value)
    
    # store information about your data
    run.store("data_n_features", X.shape[0])
    run.store("data_n_observations", X.shape[1])
    
    # store the F1 score on the train data
    run.store("metrics_train_f1_score", f1_score(y, model.predict(X), average="weighted"))
    
    # you can even store a pickled version of your model on disk
    run.store("model", model, pickled=True)
    ```
    
    After running this code, we can retrieve the stored information by calling `run.data(resolve=True)`:
    
        {'_id': 'mlflow-like-run',
         'data_n_features': 150,
         'data_n_observations': 4,
         'metrics_train_f1_score': 0.9599839935974389,
         'model': LogisticRegression(C=0.1, max_iter=200),
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
    
    This approach is straightforward: one scalar for each key in the document. However, one downside is that you need to maintain your own namespace convention. For example here, we used underscores to separate the different levels of information (params, data, metrics, etc) but this can quickly get confusing if chosen incorrectly: is it `params/model/fit_intercept` or `params/model_fit/intercept`? It is also more work than needed when information already comes nicely organized (e.g. `model.get_params()`).

3.  `yamlett` tracking

    The method we propose in this package leverages Python dictionaries / NoSQL DB documents to automatically store your information in a structured way. Let's see what it looks like using the same run as above:
    
    ```jupyter-python
    from yamlett import Run
    from sklearn.metrics import f1_score
    
    run = Run(id="yamlett-run")
    
    # store your model information
    model_info = {
        "class": model.__class__.__name__,
        "params": model.get_params(),
    }
    run.store(f"model", model_info)
    
    # store information about your data
    run.store("data", {"n_features": X.shape[0], "n_observations": X.shape[1]})
    
    # store the F1 score on your train data
    run.store("metrics.f1_score", f1_score(y, model.predict(X), average="weighted"))
    
    # you can even store a pickled version of your model on disk
    run.store("model.artifact", model, pickled=True)
    ```
    
    Once again, let's call `run.data(resolve=True)` and see what information we stored:
    
        {'_id': 'yamlett-run',
         'data': <Box: {'n_features': 150, 'n_observations': 4}>,
         'metrics': <Box: {'f1_score': 0.9599839935974389}>,
         'model': {'artifact': LogisticRegression(C=0.1, max_iter=200),
                   'class': 'LogisticRegression',
                   'params': {'C': 0.1,
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
    
    The run information is now stored in a document that can be easily parsed based on its structure. The top level keys of the document are `data`, `metrics`, and `model` making it easier to find information than with long keys in a flat dictionary. For instance, you may want to look at all the metrics for a given run using `run.data()["metrics"]`.
    
        <Box: {'f1_score': 0.9599839935974389}>
    
    Note that `yamlett` does not impose the document hierarchy so you are free to organize your run data as you see fit. Additionally, because `yamlett` is a light abstraction layer on top of MongoDB, you can query runs in an `Experiment` using `find` or `aggregate`. For example, we can retrieve all runs in the default experiment for which:
    
    1.  the model was fit with a bias term
    2.  on a dataset with at least 3000 data points
    3.  that yielded an F1 score of at least 0.9
    
    ```jupyter-python
    from yamlett import Experiment
    
    e = Experiment()
    
    e.find(
        {
            "model.params.fit_intercept": True,
            "data.n_observations": {"$gte": 3000},
            "metrics.f1_score": {"$gte": 0.9},
        }
    )
    ```


<a id="orga271eb5"></a>

### Storing large artifacts

MongoDB has a [maximum document size of 16MB](https://docs.mongodb.com/manual/reference/limits/#BSON-Document-Size). This means that storing large models or outputs along with the run information is not directly possible. `yamlett` still lets you do that with `run.store(key, value, pickled=True)`. When `pickled` is set to `True`, the passed `value` is not directly stored in MongoDB but it is pickled and stored "on disk". By default, your `run` object will store such pickled values in a `.yamlett` folder in the current working directory. However, you can change this by specifying a `path` when you instantiate your `Run`: this path can be a local path or a cloud-based path.
