<?php

use Illuminate\Support\Facades\Route;

Route::get('/', fn () => redirect()->route('dashboard.summary'));

Route::prefix('dashboard')->group(function () {
    Route::view('/summary', 'dashboard.summary')->name('dashboard.summary');
    Route::view('/stationarity', 'dashboard.stationarity')->name('dashboard.stationarity');
    Route::view('/granger', 'dashboard.granger')->name('dashboard.granger');
    Route::view('/cointegration', 'dashboard.cointegration')->name('dashboard.cointegration');
    Route::view('/toda-yamamoto', 'dashboard.toda-yamamoto')->name('dashboard.toda-yamamoto');
    Route::view('/forecast', 'dashboard.forecast')->name('dashboard.forecast');
    Route::view('/irf', 'dashboard.irf')->name('dashboard.irf');
    Route::view('/fevd', 'dashboard.fevd')->name('dashboard.fevd');
});
