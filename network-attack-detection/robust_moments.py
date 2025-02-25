"""
Robust moments (skewness, kurtosis, location and covariance) estimators.

Here are implemented estimators that are resistant to outliers.

"""
# Author: Thiago Vieira <tpbvieira@gmail.com>
#
# License: BSD 3 clause
#
# This is a fork of MinCovDet class of Virgile Fritsch, which implements Fast Minimum Covariance Determinant (Fast MCD).
# Fast NCD is an algorithm by Rousseeuw & Van Driessen described in (A Fast Algorithm for the Minimum Covariance
# Determinant Estimator, 1999, American Statistical Association and the American Society for Quality, TECHNOMETRICS)

import warnings
import numbers
import numpy as np
from scipy import linalg
from scipy.stats import chi2, skew, kurtosis
from sklearn.covariance import empirical_covariance, EmpiricalCovariance
from sklearn.utils.extmath import fast_logdet
from sklearn.utils import check_random_state, check_array


def c_step(X, n_support, remaining_iterations=30, initial_estimates=None, verbose=False, cov_computation_method=empirical_covariance, random_state=None):
    """C_step procedure described in [Rouseeuw1984]_ aiming at computing MCD.

    Parameters
    ----------
    X : array-like, shape (n_samples, n_features)
        Data set in which we look for the n_support observations whose
        scatter matrix has minimum determinant.

    n_support : int, > n_samples / 2
        Number of observations to compute the robust estimates of location
        and covariance from.

    remaining_iterations : int, optional
        Number of iterations to perform.
        According to [Rouseeuw1999]_, two iterations are sufficient to get
        close to the minimum, and we never need more than 30 to reach
        convergence.

    initial_estimates : 2-tuple, optional
        Initial estimates of location and shape from which to run the c_step
        procedure:
        - initial_estimates[0]: an initial location estimate
        - initial_estimates[1]: an initial covariance estimate

    verbose : boolean, optional
        Verbose mode.

    random_state : int, RandomState instance or None, optional (default=None)
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.

    cov_computation_method : callable, default empirical_covariance
        The function which will be used to compute the covariance.
        Must return shape (n_features, n_features)

    Returns
    -------
    location : array-like, shape (n_features,)
        Robust location estimates.

    covariance : array-like, shape (n_features, n_features)
        Robust covariance estimates.

    det : scalar. minimum determinant

    support : array-like, shape (n_samples,)
        A mask for the `n_support` observations whose scatter matrix has
        minimum determinant.

    dist : array-like, shape (n_features,), with distances of the data centered to location and scatter

    moments : array of array containing array-like, shape (n_features,)
        The skewness, kurtosis, skewness distance and kurtosis distance to the original data subtracted of skewness or
        kurtosis

    References
    ----------
    .. [Rouseeuw1999] A Fast Algorithm for the Minimum Covariance Determinant
        Estimator, 1999, American Statistical Association and the American
        Society for Quality, TECHNOMETRICS

    """
    X = np.asarray(X)
    random_state = check_random_state(random_state)
    return _c_step(X, n_support, remaining_iterations=remaining_iterations, initial_estimates=initial_estimates, verbose=verbose, cov_computation_method=cov_computation_method, random_state=random_state)


def _c_step(X, n_support, random_state, remaining_iterations=30, initial_estimates=None, verbose=False, cov_computation_method=empirical_covariance):
    n_samples, n_features = X.shape
    dist = np.inf

    # Initialisation
    support = np.zeros(n_samples, dtype=bool)
    if initial_estimates is None:
        # compute initial robust estimates from a random subset
        support[random_state.permutation(n_samples)[:n_support]] = True
    else:
        # get initial robust estimates from the function parameters
        location = initial_estimates[0]
        covariance = initial_estimates[1]
        # run a special iteration for that case (to get an initial support)
        precision = linalg.pinvh(covariance)
        X_centered = X - location
        dist = (np.dot(X_centered, precision) * X_centered).sum(1)
        # compute new estimates
        support[np.argsort(dist)[:n_support]] = True

    X_support = X[support]
    location = X_support.mean(0)
    covariance = cov_computation_method(X_support)

    # Iterative procedure for Minimum Covariance Determinant computation
    det = fast_logdet(covariance)
    # If the data already has singular covariance, calculate the precision, as the loop below will not be entered.
    if np.isinf(det):
        precision = linalg.pinvh(covariance)

    previous_det = np.inf
    while (det < previous_det and remaining_iterations > 0 and not np.isinf(det)):
        # save old estimates values
        previous_location = location
        previous_covariance = covariance
        previous_det = det
        previous_support = support
        # compute a new support from the full data set mahalanobis distances
        precision = linalg.pinvh(covariance)
        X_centered = X - location
        dist = (np.dot(X_centered, precision) * X_centered).sum(axis=1)
        # compute new estimates
        support = np.zeros(n_samples, dtype=bool)
        support[np.argsort(dist)[:n_support]] = True
        X_support = X[support]
        location = X_support.mean(axis=0)
        covariance = cov_computation_method(X_support)
        det = fast_logdet(covariance)
        # update remaining iterations for early stopping
        remaining_iterations -= 1

    previous_dist = dist
    dist = (np.dot(X - location, precision) * (X - location)).sum(axis=1)

    # after the minimum convariance determinant, compute skewness and kurtosis from X_support, which is the original X observations with minimum covariance determinant
    skew1 = skew(X_support, axis=0, bias=True)
    skew1_dist = (np.dot(X - skew1, precision) * (X - skew1)).sum(axis=1)
    kurt1 = kurtosis(X_support, axis=0, fisher=True, bias=True)
    kurt1_dist = (np.dot(X - kurt1, precision) * (X - kurt1)).sum(axis=1)
    moments = skew1, kurt1, skew1_dist, kurt1_dist

    # Check if best fit already found (det => 0, logdet => -inf)
    if np.isinf(det):
        results = location, covariance, det, support, dist, moments

    # Check convergence
    if np.allclose(det, previous_det):
        # c_step procedure converged
        if verbose:
            print("Optimal couple (location, covariance) found before ending iterations (%d left)" % (remaining_iterations))
        results = location, covariance, det, support, dist, moments
    elif det > previous_det:
        # determinant has increased (should not happen)
        warnings.warn("Warning! det > previous_det (%.15f > %.15f)" % (det, previous_det), RuntimeWarning)
        results = previous_location, previous_covariance, previous_det, previous_support, previous_dist, moments

    # Check early stopping
    if remaining_iterations == 0:
        if verbose:
            print('Maximum number of iterations reached')
        results = location, covariance, det, support, dist, moments

    return results


def select_candidates(X, n_support, n_trials, select=1, n_iter=30, verbose=False, cov_computation_method=empirical_covariance, random_state=None):
    """Finds the best pure subset of observations to compute MCD from it.

    The purpose of this function is to find the best sets of n_support
    observations with respect to a minimization of their covariance
    matrix determinant. Equivalently, it removes n_samples-n_support
    observations to construct what we call a pure data set (i.e. not
    containing outliers). The list of the observations of the pure
    data set is referred to as the `support`.

    Starting from a random support, the pure data set is found by the
    c_step procedure introduced by Rousseeuw and Van Driessen in
    [RV]_.

    Parameters
    ----------
    X : array-like, shape (n_samples, n_features)
        Data (sub)set in which we look for the n_support purest observations.

    n_support : int, [(n + p + 1)/2] < n_support < n
        The number of samples the pure data set must contain.

    select : int, int > 0
        Number of best candidates results to return.

    n_trials : int, nb_trials > 0 or 2-tuple
        Number of different initial sets of observations from which to
        run the algorithm.
        Instead of giving a number of trials to perform, one can provide a
        list of initial estimates that will be used to iteratively run
        c_step procedures. In this case:
        - n_trials[0]: array-like, shape (n_trials, n_features)
          is the list of `n_trials` initial location estimates
        - n_trials[1]: array-like, shape (n_trials, n_features, n_features)
          is the list of `n_trials` initial covariances estimates

    n_iter : int, nb_iter > 0
        Maximum number of iterations for the c_step procedure.
        (2 is enough to be close to the final solution. "Never" exceeds 20).

    random_state : int, RandomState instance or None, optional (default=None)
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.

    cov_computation_method : callable, default empirical_covariance
        The function which will be used to compute the covariance.
        Must return shape (n_features, n_features)

    verbose : boolean, default False
        Control the output verbosity.

    See Also
    ---------
    c_step

    Returns
    -------
    best_locations : array-like, shape (select, n_features)
        The `select` location estimates computed from the `select` best
        supports found in the data set (`X`).

    best_covariances : array-like, shape (select, n_features, n_features)
        The `select` covariance estimates computed from the `select`
        best supports found in the data set (`X`).

    best_supports : array-like, shape (select, n_samples)
        The `select` best supports found in the data set (`X`).

    best_moments : array of array containing array-like, shape (n_features,)
        The `select` best moments skewness, kurtosis, skewness distance and kurtosis distance to the original data
        subtracted of skewness or kurtosis,found in the data set (`X`).


    References
    ----------
    .. [RV] A Fast Algorithm for the Minimum Covariance Determinant
        Estimator, 1999, American Statistical Association and the American
        Society for Quality, TECHNOMETRICS

    """
    random_state = check_random_state(random_state)
    n_samples, n_features = X.shape

    if isinstance(n_trials, numbers.Integral):
        run_from_estimates = False
    elif isinstance(n_trials, tuple):
        run_from_estimates = True
        estimates_list = n_trials
        n_trials = estimates_list[0].shape[0]
    else:
        raise TypeError("Invalid 'n_trials' parameter, expected tuple or "
                        " integer, got %s (%s)" % (n_trials, type(n_trials)))

    # compute `n_trials` location and shape estimates candidates in the subset
    all_estimates = []
    if not run_from_estimates:
        # perform `n_trials` computations from random initial supports
        for j in range(n_trials):
            all_estimates.append(_c_step(X, n_support, remaining_iterations=n_iter, verbose=verbose, cov_computation_method=cov_computation_method, random_state=random_state))
    else:
        # perform computations from every given initial estimates
        for j in range(n_trials):
            initial_estimates = (estimates_list[0][j], estimates_list[1][j])
            all_estimates.append(_c_step(X, n_support, remaining_iterations=n_iter, initial_estimates=initial_estimates, verbose=verbose, cov_computation_method=cov_computation_method, random_state=random_state))

    all_locs_sub, all_covs_sub, all_dets_sub, all_supports_sub, all_ds_sub, all_moments_sub = zip(*all_estimates)
    all_skew1_sub, all_kurt1_sub, all_skew1_dist_sub, all_kurt1_dist_sub = zip(*all_moments_sub)

    # find the `n_best` best results among the `n_trials` ones
    index_best = np.argsort(all_dets_sub)[:select]
    best_locations = np.asarray(all_locs_sub)[index_best]
    best_covariances = np.asarray(all_covs_sub)[index_best]
    best_supports = np.asarray(all_supports_sub)[index_best]
    best_ds = np.asarray(all_ds_sub)[index_best]
    # find the `n_best` best results for moments among the `n_trials` ones
    best_skew1 = np.asarray(all_skew1_sub)[index_best]
    best_kurt1 = np.asarray(all_kurt1_sub)[index_best]
    best_skew1_dist = np.asarray(all_skew1_dist_sub)[index_best]
    best_kurt1_dist = np.asarray(all_kurt1_dist_sub)[index_best]
    best_moments = best_skew1, best_kurt1, best_skew1_dist, best_kurt1_dist

    return best_locations, best_covariances, best_supports, best_ds, best_moments


def fast_mcd(X, support_fraction=None, cov_computation_method=empirical_covariance, random_state=None):
    """Estimates the Minimum Covariance Determinant matrix.

    Read more in the :ref:`User Guide <robust_covariance>`.

    Parameters
    ----------
    X : array-like, shape (n_samples, n_features)
      The data matrix, with p features and n samples.

    support_fraction : float, 0 < support_fraction < 1
          The proportion of points to be included in the support of the raw
          MCD estimate. Default is None, which implies that the minimum
          value of support_fraction will be used within the algorithm:
          `[n_sample + n_features + 1] / 2`.

    cov_computation_method : callable, default empirical_covariance
        The function which will be used to compute the covariance.
        Must return shape (n_features, n_features)

    random_state : int, RandomState instance or None, optional (default=None)
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.

    Notes
    -----
    The FastMCD algorithm has been introduced by Rousseuw and Van Driessen
    in "A Fast Algorithm for the Minimum Covariance Determinant Estimator,
    1999, American Statistical Association and the American Society
    for Quality, TECHNOMETRICS".
    The principle is to compute robust estimates and random subsets before
    pooling them into a larger subsets, and finally into the full data set.
    Depending on the size of the initial sample, we have one, two or three
    such computation levels.

    Note that only raw estimates are returned. If one is interested in
    the correction and reweighting steps described in [RouseeuwVan]_,
    see the MinCovDet object.

    References
    ----------

    .. [RouseeuwVan] A Fast Algorithm for the Minimum Covariance
        Determinant Estimator, 1999, American Statistical Association
        and the American Society for Quality, TECHNOMETRICS

    .. [Butler1993] R. W. Butler, P. L. Davies and M. Jhun,
        Asymptotics For The Minimum Covariance Determinant Estimator,
        The Annals of Statistics, 1993, Vol. 21, No. 3, 1385-1400

    Returns
    -------
    location : array-like, shape (n_features,)
        Robust location of the data.

    covariance : array-like, shape (n_features, n_features)
        Robust covariance of the features.

    support : array-like, type boolean, shape (n_samples,)
        A mask of the observations that have been used to compute
        the robust location and covariance estimates of the data set.

    moments : array of array containing array-like, shape (n_features,), robust skewness, robust kurtosis, skewness
        distance and kurtosis distance to the original data subtracted of skewness or kurtosis.

    """
    random_state = check_random_state(random_state)

    X = check_array(X, ensure_min_samples=2, estimator='fast_mcd')
    n_samples, n_features = X.shape

    # minimum breakdown value
    if support_fraction is None:
        n_support = int(np.ceil(0.5 * (n_samples + n_features + 1)))
    else:
        n_support = int(support_fraction * n_samples)

    # 1-dimensional case quick computation
    # (Rousseeuw, P. J. and Leroy, A. M. (2005) References, in Robust
    #  Regression and Outlier Detection, John Wiley & Sons, chapter 4)
    if n_features == 1:
        if n_support < n_samples:
            # find the sample shortest halves
            X_sorted = np.sort(np.ravel(X))
            diff = X_sorted[n_support:] - X_sorted[:(n_samples - n_support)]
            halves_start = np.where(diff == np.min(diff))[0]
            # take the middle points' mean to get the robust location estimate
            location = 0.5 * (X_sorted[n_support + halves_start] + X_sorted[halves_start]).mean()
            support = np.zeros(n_samples, dtype=bool)
            X_centered = X - location
            support[np.argsort(np.abs(X_centered), 0)[:n_support]] = True
            covariance = np.asarray([[np.var(X[support])]])
            location = np.array([location])
            # get precision matrix in an optimized way
            precision = linalg.pinvh(covariance)
            dist = (np.dot(X_centered, precision) * (X_centered)).sum(axis=1)
        else:
            support = np.ones(n_samples, dtype=bool)
            covariance = np.asarray([[np.var(X)]])
            location = np.asarray([np.mean(X)])
            X_centered = X - location
            # get precision matrix in an optimized way
            precision = linalg.pinvh(covariance)
            dist = (np.dot(X_centered, precision) * (X_centered)).sum(axis=1)
        # Starting FastMCD algorithm for p-dimensional case
    if (n_samples > 500) and (n_features > 1):
        # 1. Find candidate supports on subsets
        # a. split the set in subsets of size ~ 300
        n_subsets = n_samples // 300
        n_samples_subsets = n_samples // n_subsets
        samples_shuffle = random_state.permutation(n_samples)
        h_subset = int(np.ceil(n_samples_subsets * (n_support / float(n_samples))))
        # b. perform a total of 500 trials
        n_trials_tot = 500
        # c. select 10 best (location, covariance) for each subset
        n_best_sub = 10
        n_trials = max(10, n_trials_tot // n_subsets)
        n_best_tot = n_subsets * n_best_sub
        all_best_locations = np.zeros((n_best_tot, n_features))
        try:
            all_best_covariances = np.zeros((n_best_tot, n_features, n_features))
        except MemoryError:
            # The above is too big. Let's try with something much small
            # (and less optimal)
            all_best_covariances = np.zeros((n_best_tot, n_features, n_features))
            n_best_tot = 10
            n_best_sub = 2
        for i in range(n_subsets):
            low_bound = i * n_samples_subsets
            high_bound = low_bound + n_samples_subsets
            current_subset = X[samples_shuffle[low_bound:high_bound]]
            best_locations_sub, best_covariances_sub, _, _, _ = select_candidates(current_subset, h_subset, n_trials,select=n_best_sub, n_iter=2,cov_computation_method=cov_computation_method,random_state=random_state)
            subset_slice = np.arange(i * n_best_sub, (i + 1) * n_best_sub)
            all_best_locations[subset_slice] = best_locations_sub
            all_best_covariances[subset_slice] = best_covariances_sub

        # 2. Pool the candidate supports into a merged set (possibly the full dataset)
        n_samples_merged = min(1500, n_samples)
        h_merged = int(np.ceil(n_samples_merged * (n_support / float(n_samples))))
        if n_samples > 1500:
            n_best_merged = 10
        else:
            n_best_merged = 1

        # find the best couples (location, covariance) on the merged set
        selection = random_state.permutation(n_samples)[:n_samples_merged]
        locations_merged, covariances_merged, supports_merged, d, moments_merged = \
            select_candidates(X[selection], h_merged, n_trials=(all_best_locations, all_best_covariances), select=n_best_merged, cov_computation_method=cov_computation_method, random_state=random_state)

        # 3. Finally get the overall best (locations, covariance) couple
        if n_samples < 1500:
            # directly get the best couple (location, covariance)
            location = locations_merged[0]
            covariance = covariances_merged[0]
            support = np.zeros(n_samples, dtype=bool)
            dist = np.zeros(n_samples)
            support[selection] = supports_merged[0]
            dist[selection] = d[0]
            # moments
            skew1_merged, kurt1_merged, skew1_dist_merged, kurt1_dist_merged = moments_merged
            skew1 = skew1_merged[0]
            kurt1 = kurt1_merged[0]
            skew1_dist = skew1_dist_merged[0]
            kurt1_dist = kurt1_dist_merged[0]
        else:
            # select the best couple on the full dataset
            locations_full, covariances_full, supports_full, d, moments_full = select_candidates(X, n_support,n_trials=(locations_merged, covariances_merged),select=1,cov_computation_method=cov_computation_method,random_state=random_state)
            location = locations_full[0]
            covariance = covariances_full[0]
            support = supports_full[0]
            dist = d[0]
            # moments
            skew1_full, kurt1_full, skew1_dist_full, kurt1_dist_full = moments_full
            skew1 = skew1_full[0]
            kurt1 = kurt1_full[0]
            skew1_dist = skew1_dist_full[0]
            kurt1_dist = kurt1_dist_full[0]
    elif n_features > 1:
        # 1. Find the 10 best couples (location, covariance)
        # considering two iterations
        n_trials = 30
        n_best = 10
        locations_best, covariances_best, _, _, _ = select_candidates(X, n_support, n_trials=n_trials, select=n_best, n_iter=2,cov_computation_method=cov_computation_method,random_state=random_state)

        # 2. Select the best couple on the full dataset amongst the 10
        locations_full, covariances_full, supports_full, d, moments_full = select_candidates(X, n_support, n_trials=(locations_best, covariances_best),select=1, cov_computation_method=cov_computation_method,random_state=random_state)
        location = locations_full[0]
        covariance = covariances_full[0]
        support = supports_full[0]
        dist = d[0]
        # moments
        skew1_full, kurt1_full, skew1_dist_full, kurt1_dist_full = moments_full
        skew1 = skew1_full[0]
        kurt1 = kurt1_full[0]
        skew1_dist = skew1_dist_full[0]
        kurt1_dist = kurt1_dist_full[0]

    moments = skew1, kurt1, skew1_dist, kurt1_dist

    return location, covariance, support, dist, moments


class MomentMinCovDet(EmpiricalCovariance):
    """Minimum Covariance Determinant (MCD): robust estimator of covariance.

    The Minimum Covariance Determinant covariance estimator is to be applied
    on Gaussian-distributed data, but could still be relevant on data
    drawn from a unimodal, symmetric distribution. It is not meant to be used
    with multi-modal data (the algorithm used to fit a MinCovDet object is
    likely to fail in such a case).
    One should consider projection pursuit methods to deal with multi-modal
    datasets.

    Read more in the :ref:`User Guide <robust_covariance>`.

    Parameters
    ----------
    store_precision : bool
        Specify if the estimated precision is stored.

    assume_centered : Boolean
        If True, the support of the robust location and the covariance
        estimates is computed, and a covariance estimate is recomputed from
        it, without centering the data.
        Useful to work with data whose mean is significantly equal to
        zero but is not exactly zero.
        If False, the robust location and covariance are directly computed
        with the FastMCD algorithm without additional treatment.

    support_fraction : float, 0 < support_fraction < 1
        The proportion of points to be included in the support of the raw
        MCD estimate. Default is None, which implies that the minimum
        value of support_fraction will be used within the algorithm:
        [n_sample + n_features + 1] / 2

    random_state : int, RandomState instance or None, optional (default=None)
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.

    Attributes
    ----------
    raw_location_ : array-like, shape (n_features,)
        The raw robust estimated location before correction and re-weighting.

    raw_covariance_ : array-like, shape (n_features, n_features)
        The raw robust estimated covariance before correction and re-weighting.

    raw_support_ : array-like, shape (n_samples,)
        A mask of the observations that have been used to compute
        the raw robust estimates of location and shape, before correction
        and re-weighting.

    raw_skew1_ : array-like, shape (n_features,)
        The raw robust estimated skewness

    raw_kurt1_ : array-like, shape (n_features,)
        The raw robust estimated kurtosis

    location_ : array-like, shape (n_features,)
        Estimated robust location (corrected for consistency)

    covariance_ : array-like, shape (n_features, n_features)
        Estimated robust covariance matrix (corrected for consistency)

    precision_ : array-like, shape (n_features, n_features)
        Estimated pseudo inverse matrix. (stored only if store_precision is True)

    support_ : array-like, shape (n_samples,)
        A mask of the observations that have been used to compute the robust estimates of location and shape.

    dist_ : array-like, shape (n_samples,)
        Mahalanobis distances of the training set (on which `fit` is called) observations.

    raw_skew1_dist_ : array-like, shape (n_samples,)
        Mahalanobis Skewness distances of the training set (on which `fit` is called) observations.

    raw_kurt1_dist_ : array-like, shape (n_samples,)
        Mahalanobis Kurtosis distances of the training set (on which `fit` is called) observations.

    References
    ----------

    .. [Rouseeuw1984] `P. J. Rousseeuw. Least median of squares regression. J. Am Stat Ass, 79:871, 1984.`
    .. [Rousseeuw] `A Fast Algorithm for the Minimum Covariance Determinant Estimator, 1999, American Statistical
        Association and the American Society for Quality, TECHNOMETRICS`
    .. [ButlerDavies] `R. W. Butler, P. L. Davies and M. Jhun, Asymptotics For The Minimum Covariance Determinant
        Estimator, The Annals of Statistics, 1993, Vol. 21, No. 3, 1385-1400`

    """
    _nonrobust_covariance = staticmethod(empirical_covariance)

    def __init__(self, store_precision=True, assume_centered=False,support_fraction=None, random_state=None):
        self.store_precision = store_precision
        self.assume_centered = assume_centered
        self.support_fraction = support_fraction
        self.random_state = random_state

    def fit(self, X, y=None):
        """Fits a Minimum Covariance Determinant with the FastMCD algorithm.

        Parameters
        ----------
        X : array-like, shape = [n_samples, n_features]
            Training data, where n_samples is the number of samples
            and n_features is the number of features.

        y : not used, present for API consistence purpose.

        Returns
        -------
        self : object
            Returns self.

        """
        X = check_array(X, ensure_min_samples=2, estimator='MinCovDet')
        random_state = check_random_state(self.random_state)
        n_samples, n_features = X.shape

        # check that the empirical covariance is full rank
        if (linalg.svdvals(np.dot(X.T, X)) > 1e-8).sum() != n_features:
            warnings.warn("The covariance matrix associated to your dataset is not full rank")
        # compute and store raw estimates
        raw_location, raw_covariance, raw_support, raw_dist, raw_moments = fast_mcd(X, support_fraction=self.support_fraction,cov_computation_method=self._nonrobust_covariance,random_state=random_state)

        if self.assume_centered:
            raw_location = np.zeros(n_features)
            raw_covariance = self._nonrobust_covariance(X[raw_support],assume_centered=True)
            # get precision matrix in an optimized way
            precision = linalg.pinvh(raw_covariance)
            raw_dist = np.sum(np.dot(X, precision) * X, 1)

        self.raw_location_ = raw_location
        self.raw_covariance_ = raw_covariance
        self.raw_support_ = raw_support
        self.location_ = raw_location
        self.support_ = raw_support
        self.dist_ = raw_dist

        raw_skew1, raw_kurt1, raw_skew1_dist, raw_kurt1_dist = raw_moments
        self.raw_skew1_ = raw_skew1
        self.raw_kurt1_ = raw_kurt1
        self.raw_skew1_dist_ = raw_skew1_dist
        self.raw_kurt1_dist_ = raw_kurt1_dist

        # obtain consistency at normal models
        self.correct_covariance(X)

        # re-weight estimator
        self.reweight_covariance(X)

        return self

    def correct_covariance(self, data):
        """Apply a correction to raw Minimum Covariance Determinant estimates.

        Correction using the empirical correction factor suggested
        by Rousseeuw and Van Driessen in [RVD]_.

        Parameters
        ----------
        data : array-like, shape (n_samples, n_features)
            The data matrix, with p features and n samples.
            The data set must be the one which was used to compute
            the raw estimates.

        References
        ----------

        .. [RVD] `A Fast Algorithm for the Minimum Covariance
            Determinant Estimator, 1999, American Statistical Association
            and the American Society for Quality, TECHNOMETRICS`

        Returns
        -------
        covariance_corrected : array-like, shape (n_features, n_features)
            Corrected robust covariance estimate.

        """
        correction = np.median(self.dist_) / chi2(data.shape[1]).isf(0.5)
        covariance_corrected = self.raw_covariance_ * correction
        self.dist_ /= correction

        return covariance_corrected

    def reweight_covariance(self, data):
        """Re-weight raw Minimum Covariance Determinant estimates.

        Re-weight observations using Rousseeuw's method (equivalent to
        deleting outlying observations from the data set before
        computing location and covariance estimates) described
        in [RVDriessen]_.

        Parameters
        ----------
        data : array-like, shape (n_samples, n_features)
            The data matrix, with p features and n samples.
            The data set must be the one which was used to compute
            the raw estimates.

        References
        ----------

        .. [RVDriessen] `A Fast Algorithm for the Minimum Covariance
            Determinant Estimator, 1999, American Statistical Association
            and the American Society for Quality, TECHNOMETRICS`

        Returns
        -------
        location_reweighted : array-like, shape (n_features, )
            Re-weighted robust location estimate.

        covariance_reweighted : array-like, shape (n_features, n_features)
            Re-weighted robust covariance estimate.

        support_reweighted : array-like, type boolean, shape (n_samples,)
            A mask of the observations that have been used to compute
            the re-weighted robust location and covariance estimates.

        """
        n_samples, n_features = data.shape
        mask = self.dist_ < chi2(n_features).isf(0.025)

        if self.assume_centered:
            location_reweighted = np.zeros(n_features)
        else:
            location_reweighted = data[mask].mean(0)

        covariance_reweighted = self._nonrobust_covariance(data[mask], assume_centered=self.assume_centered)
        support_reweighted = np.zeros(n_samples, dtype=bool)
        support_reweighted[mask] = True
        self._set_covariance(covariance_reweighted)
        self.location_ = location_reweighted
        self.support_ = support_reweighted
        X_centered = data - self.location_
        self.dist_ = np.sum(np.dot(X_centered, self.get_precision()) * X_centered, 1)

        return location_reweighted, covariance_reweighted, support_reweighted