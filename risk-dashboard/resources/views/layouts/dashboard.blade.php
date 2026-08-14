<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>@yield('title', 'Risk Dashboard') — {{ config('app.name') }}</title>
    @vite(['resources/css/app.css', 'resources/js/app.js'])
</head>
<body class="min-h-screen flex antialiased">

    {{-- Sidebar --}}
    <aside class="fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r"
           style="background-color: var(--color-bg-sidebar); border-color: var(--color-border);">

        {{-- Logo --}}
        <div class="flex h-16 items-center gap-3 px-5 border-b" style="border-color: var(--color-border);">
            <div class="flex h-8 w-8 items-center justify-center rounded-lg"
                 style="background-color: var(--color-accent-blue);">
                <svg class="h-4 w-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                </svg>
            </div>
            <span class="text-sm font-semibold tracking-tight" style="color: var(--color-text-primary);">
                Risk Dashboard
            </span>
        </div>

        {{-- Navigation --}}
        <nav class="flex-1 overflow-y-auto py-4 px-3 scrollbar-thin">
            <p class="mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest"
               style="color: var(--color-text-muted);"
               data-i18n="nav.overview">
                Overview
            </p>
            <ul class="space-y-0.5">
                <li>
                    <a href="{{ route('dashboard.summary') }}"
                       class="sidebar-link group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors
                              @if(request()->routeIs('dashboard.summary')) font-medium @endif"
                       style="color: {{ request()->routeIs('dashboard.summary') ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }};
                              background-color: {{ request()->routeIs('dashboard.summary') ? 'var(--color-bg-card)' : 'transparent' }};">
                        <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"/></svg>
                        <span data-i18n="nav.summary">Summary</span>
                    </a>
                </li>
            </ul>

            <p class="mt-6 mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest"
               style="color: var(--color-text-muted);"
               data-i18n="nav.causality">
                Causality Analysis
            </p>
            <ul class="space-y-0.5">
                <li>
                    <a href="{{ route('dashboard.stationarity') }}"
                       class="sidebar-link group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors
                              @if(request()->routeIs('dashboard.stationarity')) font-medium @endif"
                       style="color: {{ request()->routeIs('dashboard.stationarity') ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }};
                              background-color: {{ request()->routeIs('dashboard.stationarity') ? 'var(--color-bg-card)' : 'transparent' }};">
                        <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
                        <span data-i18n="nav.phase1">Phase 1 — Stationarity</span>
                    </a>
                </li>
                <li>
                    <a href="{{ route('dashboard.granger') }}"
                       class="sidebar-link group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors
                              @if(request()->routeIs('dashboard.granger')) font-medium @endif"
                       style="color: {{ request()->routeIs('dashboard.granger') ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }};
                              background-color: {{ request()->routeIs('dashboard.granger') ? 'var(--color-bg-card)' : 'transparent' }};">
                        <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                        <span data-i18n="nav.phase2">Phase 2 — Granger</span>
                    </a>
                </li>
                <li>
                    <a href="{{ route('dashboard.cointegration') }}"
                       class="sidebar-link group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors
                              @if(request()->routeIs('dashboard.cointegration')) font-medium @endif"
                       style="color: {{ request()->routeIs('dashboard.cointegration') ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }};
                              background-color: {{ request()->routeIs('dashboard.cointegration') ? 'var(--color-bg-card)' : 'transparent' }};">
                        <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/></svg>
                        <span data-i18n="nav.phase3">Phase 3 — Cointegration</span>
                    </a>
                </li>
                <li>
                    <a href="{{ route('dashboard.toda-yamamoto') }}"
                       class="sidebar-link group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors
                              @if(request()->routeIs('dashboard.toda-yamamoto')) font-medium @endif"
                       style="color: {{ request()->routeIs('dashboard.toda-yamamoto') ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }};
                              background-color: {{ request()->routeIs('dashboard.toda-yamamoto') ? 'var(--color-bg-card)' : 'transparent' }};">
                        <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        <span data-i18n="nav.phase3b">Phase 3b — Toda-Yamamoto</span>
                    </a>
                </li>
            </ul>

            <p class="mt-6 mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest"
               style="color: var(--color-text-muted);"
               data-i18n="nav.forecasting">
                Forecasting
            </p>
            <ul class="space-y-0.5">
                <li>
                    <a href="{{ route('dashboard.forecast') }}"
                       class="sidebar-link group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors
                              @if(request()->routeIs('dashboard.forecast')) font-medium @endif"
                       style="color: {{ request()->routeIs('dashboard.forecast') ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }};
                              background-color: {{ request()->routeIs('dashboard.forecast') ? 'var(--color-bg-card)' : 'transparent' }};">
                        <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
                        <span data-i18n="nav.phase4">Phase 4 — Forecast</span>
                    </a>
                </li>
                <li>
                    <a href="{{ route('dashboard.irf') }}"
                       class="sidebar-link group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors
                              @if(request()->routeIs('dashboard.irf')) font-medium @endif"
                       style="color: {{ request()->routeIs('dashboard.irf') ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }};
                              background-color: {{ request()->routeIs('dashboard.irf') ? 'var(--color-bg-card)' : 'transparent' }};">
                        <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                        <span data-i18n="nav.phase5_irf">Phase 5 — IRF</span>
                    </a>
                </li>
                <li>
                    <a href="{{ route('dashboard.fevd') }}"
                       class="sidebar-link group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors
                              @if(request()->routeIs('dashboard.fevd')) font-medium @endif"
                       style="color: {{ request()->routeIs('dashboard.fevd') ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }};
                              background-color: {{ request()->routeIs('dashboard.fevd') ? 'var(--color-bg-card)' : 'transparent' }};">
                        <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"/></svg>
                        <span data-i18n="nav.phase5_fevd">Phase 5 — FEVD</span>
                    </a>
                </li>
            </ul>
        </nav>

        {{-- Footer --}}
        <div class="border-t px-5 py-3" style="border-color: var(--color-border);">
            <p class="text-[11px]" style="color: var(--color-text-muted);"
               data-i18n="nav.footer">
                Pipeline 3A · VAR on Levels
            </p>
        </div>
    </aside>

    {{-- Main content --}}
    <main class="ml-64 flex-1 min-h-screen">
        {{-- Top bar --}}
        <header class="sticky top-0 z-20 flex h-16 items-center justify-between border-b px-8"
                style="background-color: var(--color-bg-primary); border-color: var(--color-border);">
            <div>
                <h1 id="page-title" class="text-lg font-semibold" style="color: var(--color-text-primary);">
                    @yield('page-title', 'Dashboard')
                </h1>
                <p id="page-subtitle" class="text-xs" style="color: var(--color-text-muted);">
                    @yield('page-subtitle', 'Hybrid Causal Forecasting — 3-Variable System')
                </p>
            </div>
            <div class="flex items-center gap-3">
                @hasSection('export-buttons')
                    @yield('export-buttons')
                @endif
                <button id="lang-toggle"
                        onclick="window.setLang(window.getLang() === 'vi' ? 'en' : 'vi')"
                        class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold transition-colors cursor-pointer"
                        style="background-color: var(--color-bg-card); color: var(--color-accent-cyan); border: 1px solid var(--color-border);">
                    EN
                </button>
                <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
                      style="background-color: var(--color-bg-card); color: var(--color-text-secondary);">
                    <span class="h-1.5 w-1.5 rounded-full" style="background-color: var(--color-kpi-positive);"></span>
                    <span data-i18n="header.read_only">READ-ONLY</span>
                </span>
            </div>
        </header>

        {{-- Pipeline Stepper --}}
        @unless(request()->routeIs('dashboard.summary'))
        @php
            $steps = [
                ['label' => 'Stationarity',   'num' => 1, 'routes' => ['dashboard.stationarity']],
                ['label' => 'Granger',         'num' => 2, 'routes' => ['dashboard.granger']],
                ['label' => 'Cointegration',   'num' => 3, 'routes' => ['dashboard.cointegration', 'dashboard.toda-yamamoto']],
                ['label' => 'Forecast',        'num' => 4, 'routes' => ['dashboard.forecast']],
                ['label' => 'IRF & FEVD',      'num' => 5, 'routes' => ['dashboard.irf', 'dashboard.fevd']],
            ];
            $currentStep = 0;
            foreach ($steps as $i => $step) {
                foreach ($step['routes'] as $route) {
                    if (request()->routeIs($route)) {
                        $currentStep = $i + 1;
                        break 2;
                    }
                }
            }
        @endphp
        <div class="px-8 pt-6">
            <div class="pipeline-stepper">
                @foreach($steps as $i => $step)
                    @php
                        $stepNum = $i + 1;
                        $state = $stepNum < $currentStep ? 'completed' : ($stepNum === $currentStep ? 'active' : 'future');
                    @endphp

                    @if($i > 0)
                        <div class="step-connector {{ $stepNum <= $currentStep ? ($stepNum === $currentStep ? 'flow' : 'completed') : '' }}"></div>
                    @endif

                    <div class="step-node {{ $state }}">
                        <div class="step-dot">
                            @if($state === 'completed')
                                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>
                            @else
                                {{ $step['num'] }}
                            @endif
                        </div>
                        <span class="step-label" data-i18n="stepper.{{ $step['num'] }}">{{ $step['label'] }}</span>
                    </div>
                @endforeach
            </div>
        </div>
        @endunless

        {{-- Page content --}}
        <div class="p-8 @unless(request()->routeIs('dashboard.summary')) pt-2 @endunless">
            @yield('content')
        </div>
    </main>

    @stack('scripts')
</body>
</html>
