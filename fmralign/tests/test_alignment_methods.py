# -*- coding: utf-8 -*-

import numpy as np
from numpy.testing import assert_array_almost_equal
from scipy.sparse import csc_matrix
from scipy.linalg import orthogonal_procrustes

# add directory to path
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fmralign.alignment_methods import (
    DiagonalAlignment,
    Hungarian,
    Identity,
    OptimalTransportAlignment,
    POTAlignment,
    RidgeAlignment,
    ScaledOrthogonalAlignment,
    Hyperalignment as INT,
    _voxelwise_signal_projection,
    optimal_permutation,
    scaled_procrustes,
)
from fmralign.tests.utils import zero_mean_coefficient_determination
from fmralign.generate_data import (
    generate_dummy_signal,
    generate_dummy_searchlights,
)

from hyperalignment.regions import create_parcels_from_labels
import os
import shutil


def test_scaled_procrustes_algorithmic():
    """Test Scaled procrustes"""
    X = np.random.randn(10, 20)
    Y = np.zeros_like(X)
    R = np.eye(X.shape[1])
    R_test, _ = scaled_procrustes(X, Y)
    assert_array_almost_equal(R, R_test)

    """Test if scaled_procrustes basis is orthogonal"""
    X = np.random.rand(3, 4)
    X = X - X.mean(axis=1, keepdims=True)

    Y = np.random.rand(3, 4)
    Y = Y - Y.mean(axis=1, keepdims=True)

    R, _ = scaled_procrustes(X.T, Y.T)
    assert_array_almost_equal(R.dot(R.T), np.eye(R.shape[0]))
    assert_array_almost_equal(R.T.dot(R), np.eye(R.shape[0]))

    """ Test if it sticks to scipy scaled procrustes in a simple case"""
    X = np.random.rand(4, 4)
    Y = np.random.rand(4, 4)

    R, _ = scaled_procrustes(X, Y)
    R_s, _ = orthogonal_procrustes(Y, X)
    assert_array_almost_equal(R.T, R_s)

    """Test that primal and dual give same results"""
    # number of samples n , number of voxels p
    n, p = 100, 20
    X = np.random.randn(n, p)
    Y = np.random.randn(n, p)
    R1, s1 = scaled_procrustes(X, Y, scaling=True, primal=True)
    R_s, _ = orthogonal_procrustes(Y, X)
    R2, s2 = scaled_procrustes(X, Y, scaling=True, primal=False)
    assert_array_almost_equal(R1, R2)
    assert_array_almost_equal(R2, R_s.T)
    n, p = 20, 100
    X = np.random.randn(n, p)
    Y = np.random.randn(n, p)
    R1, s1 = scaled_procrustes(X, Y, scaling=True, primal=True)
    R_s, _ = orthogonal_procrustes(Y, X)
    R2, s2 = scaled_procrustes(X, Y, scaling=True, primal=False)
    assert_array_almost_equal(s1 * X.dot(R1), s2 * X.dot(R2))


def test_scaled_procrustes_on_simple_exact_cases():
    """Orthogonal Matrix"""
    v = 10
    k = 10
    rnd_matrix = np.random.rand(v, k)
    R, _ = np.linalg.qr(rnd_matrix)
    X = np.random.rand(10, 20)
    X = X - X.mean(axis=1, keepdims=True)
    Y = R.dot(X)
    R_test, _ = scaled_procrustes(X.T, Y.T)
    assert_array_almost_equal(R_test.T, R)

    """Scaled Matrix"""
    X = np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 3.0, 4.0, 6.0], [7.0, 8.0, -5.0, -2.0]])

    X = X - X.mean(axis=1, keepdims=True)

    Y = 2 * X
    Y = Y - Y.mean(axis=1, keepdims=True)

    assert_array_almost_equal(scaled_procrustes(X.T, Y.T, scaling=True)[0], np.eye(3))
    assert_array_almost_equal(scaled_procrustes(X.T, Y.T, scaling=True)[1], 2)

    """3D Rotation"""
    R = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, np.cos(1), -np.sin(1)],
            [0.0, np.sin(1), np.cos(1)],
        ]
    )
    X = np.random.rand(3, 4)
    X = X - X.mean(axis=1, keepdims=True)
    Y = R.dot(X)

    R_test, _ = scaled_procrustes(X.T, Y.T)
    assert_array_almost_equal(
        R.dot(np.array([0.0, 1.0, 0.0])), np.array([0.0, np.cos(1), np.sin(1)])
    )
    assert_array_almost_equal(
        R.dot(np.array([0.0, 0.0, 1.0])), np.array([0.0, -np.sin(1), np.cos(1)])
    )
    assert_array_almost_equal(R, R_test.T)

    """Test Scaled_Orthogonal_Alignment on an exact case"""
    ortho_al = ScaledOrthogonalAlignment(scaling=False)
    ortho_al.fit(X.T, Y.T)
    assert_array_almost_equal(ortho_al.transform(X.T), Y.T)


def test_optimal_permutation_on_translation_case():
    """Test optimal permutation method"""
    X = np.array([[1.0, 4.0, 10], [1.5, 5, 10], [1, 5, 11], [1, 5.5, 8]]).T
    # translate the data matrix along features axis (voxels are permutated)
    Y = np.roll(X, 2, axis=1)

    opt = optimal_permutation(X, Y).toarray()
    assert_array_almost_equal(opt.dot(X.T).T, Y)

    U = np.vstack([X.T, 2 * X.T])
    V = np.roll(U, 4, axis=1)

    opt = optimal_permutation(U, V).toarray()
    assert_array_almost_equal(opt.dot(U.T).T, V)


def test_projection_coefficients():
    n_samples = 4
    n_features = 6
    A = np.random.rand(n_samples, n_features)
    C = []
    for i, a in enumerate(A):
        C.append((i + 1) * a)
    c = _voxelwise_signal_projection(A, C, 2)
    assert_array_almost_equal(c, [i + 1 for i in range(n_samples)])


def test_all_classes_R_and_pred_shape_and_better_than_identity():
    """Test all classes on random case"""
    # test on empty data
    X = np.zeros((30, 10))
    for algo in [
        Identity(),
        RidgeAlignment(),
        ScaledOrthogonalAlignment(),
        OptimalTransportAlignment(),
        Hungarian(),
        DiagonalAlignment(),
    ]:
        algo.fit(X, X)
        assert_array_almost_equal(algo.transform(X), X)
    # if trying to learn a fit from array of zeros to zeros (empty parcel)
    # every algo will return a zero matrix
    for n_samples, n_features in [(100, 20), (20, 100)]:
        X = np.random.randn(n_samples, n_features)
        Y = np.random.randn(n_samples, n_features)
        id = Identity()
        id.fit(X, Y)
        identity_baseline_score = zero_mean_coefficient_determination(Y, X)
        assert_array_almost_equal(X, id.transform(X))
        for algo in [
            RidgeAlignment(),
            ScaledOrthogonalAlignment(),
            ScaledOrthogonalAlignment(scaling=False),
            OptimalTransportAlignment(),
            Hungarian(),
            DiagonalAlignment(),
        ]:
            algo.fit(X, Y)
            # test that permutation matrix shape is (20, 20) except for Ridge
            if isinstance(algo.R, csc_matrix):
                R = algo.R.toarray()
                assert R.shape == (n_features, n_features)
            elif not isinstance(algo, RidgeAlignment):
                R = algo.R
                assert R.shape == (n_features, n_features)
            # test pred shape and loss improvement compared to identity
            X_pred = algo.transform(X)
            assert X_pred.shape == X.shape
            algo_score = zero_mean_coefficient_determination(Y, X_pred)
            assert algo_score >= identity_baseline_score


# %%
def test_ott_backend():
    n_samples, n_features = 100, 20
    epsilon = 0.1
    X = np.random.randn(n_samples, n_features)
    Y = np.random.randn(n_samples, n_features)
    algo = OptimalTransportAlignment(
        reg=epsilon, metric="euclidean", tol=1e-5, max_iter=10000
    )
    old_implem = POTAlignment(reg=epsilon, metric="euclidean", tol=1e-5, max_iter=10000)
    algo.fit(X, Y)
    old_implem.fit(X, Y)
    assert_array_almost_equal(algo.R, old_implem.R, decimal=3)


def test_searchlight_alignment_with_ridge():
    n_voxels = 99
    n_time_points = 149
    n_searchlights = 92
    n_subjects = 5

    radius = 20
    searchlights, dists = generate_dummy_searchlights(
        n_searchlights=n_searchlights,
        n_v=n_voxels,
        radius=radius,
        seed=0,
    )

    X_train, X_test, _, _, _ = generate_dummy_signal(
        n_t=n_time_points, n_v=n_voxels, n_s=n_subjects
    )

    model = INT()
    model.fit(X_train, searchlights, dists, radius=radius)
    X_pred = model.transform(X_test)

    # assert that the saved cached files exist
    assert_array_almost_equal(X_pred, X_test, decimal=3)
    b = os.path.exists("cache/")
    shutil.rmtree("cache")
    assert b
    assert X_pred.shape == X_test.shape


def test_parcel_alignment():
    n_voxels = 99
    n_time_points = 149
    n_subjects = 5

    n_parcels = 10
    labels = np.arange(n_voxels) % n_parcels + 1
    parcels = create_parcels_from_labels(labels)

    X_train, X_test, _, _, _ = generate_dummy_signal(
        n_t=n_time_points, n_v=n_voxels, n_s=n_subjects
    )

    model = INT(n_jobs=-1, alignment_method="parcel")
    model.fit(X_train, parcels=parcels)
    X_pred = model.transform(X_test)

    # assert that the saved cached files exist
    assert_array_almost_equal(X_pred, X_test, decimal=3)
    b = os.path.exists("cache/")
    shutil.rmtree("cache")
    assert b
    assert X_pred.shape == X_test.shape


# Cleaning up the cache folder
if os.path.exists("cache/"):
    shutil.rmtree("cache")
