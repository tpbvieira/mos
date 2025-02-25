function res = ex313(transform, K, targetPSNR, noIT, testLena, verbose)
% ex313           Training of dictionary for images using K-SVD
%                 Each 8x8 image block, or 8x8 coefficient block, are made
% into a column vector of length N = 64.
% The training set is generated by getXfrom8images (12000 vectors).
% The results are saved in 'ex313mmmddhhmm.mat'.
% 
% example:
%  res = ex313(transform, K, targetPSNR, noIT, testLena, verbose)
%-------------------------------------------------------------------------
% arguments:
%   transform   may be:  'none', 'dct', 'lot', 'elt', 'db79', 'm79'
%               see myim2col.m for more
%   K           number og vectors in dictionary
%   targetPSNR  target Peak Signal to Noise Ratio, should be >= 30
%               R = X - D*W;  % not an image (R ~= A - Ar)
%               sumRR = sum(sum(R.*R));
%               PSNR = 10*log10( numel(R)*255^2 / sumRR )
%   noIT        number of iterations through the training set
%   testLena    0 or 1, default 0. (imageapprox.m is used)
%   verbose     0 or 1, default 0.
%-------------------------------------------------------------------------
% example:
%  res = ex313('none',128,35,50);       % a simple example
%  res = ex313('m79',440,38,200,1,1);   % another example
%  res = ex313('many');     % adjust m-file to learn many dictionaries                            

%----------------------------------------------------------------------
% Copyright (c) 2009.  Karl Skretting.  All rights reserved.
% University of Stavanger.
% Mail:  karl.skretting@uis.no   Homepage:  http://www.ux.uis.no/~karlsk/
% 
% HISTORY:  dd.mm.yyyy
% Ver. 1.0  30.10.2009  KS: based on ex311.m
% Ver. 1.1  02.11.2009  KS: use ex314 to plot SNR during training
% Ver. 1.2  20.01.2010  KS: use getXfrom8images (not dataXimage)
% Ver. 1.3  09.08.2011  KS: Simplified a little bit
%----------------------------------------------

mfile = 'ex313';

if ((nargin == 1) && strcmpi(transform,'many'))
    K = 440;   % 128, 440 (DC excluded), 512
    noit = 500;
    target = 36;
    for i = 1:5
        ex313( 'm79', K, target, noit);
        ex313('none', K, target, noit);
    end
    res = 'done';
    return;
end

if (nargin < 3)
   error([mfile,': wrong number of arguments, see help.']);
end
if (nargin < 4); noIT = 500; end;
if (nargin < 5); testLena = 0; end;
if (nargin < 6); verbose = 0; end;

maxS = 40;
N = 64;
substep = 5;
noIT = substep*ceil(noIT/substep);

% limit for absolute error, ORMP end when ||r|| < maxError
% PSNR = 10*log10( numel(.)*255^2 / sum( ||r_i||^2 ) )
% setting maxError, the average error will be smaller
maxError = 1.5*sqrt(N)*255*10^(-targetPSNR/20);  
relLim = 1e-6;

%
X = getXfrom8images('t',transform, 'getFixedSet',1, 'v',1);
[N,L] = size(X);
%
disp(' ');
disp([mfile,': start K-SVD training for images, ',datestr(now()),...
    ', N=64, K=',int2str(K),', L=',int2str(L),', noIT=',int2str(noIT),...
    ', target PSNR = ',num2str(targetPSNR) ]);

% always select the DC vector, thus remove DC here
if strcmpi(transform,'none')
    X = X - ones(64,1)*mean(X);
else
    X(1,:) = zeros(1,L);
end
%
% for many training vectors the DC element will be enough
% the dictionary is trained for the rest
xsquared = sum(X.*X);   % this is ||r||^2 after DC is selected
xnorm = sqrt(xsquared);
sumXX = sum(xsquared);
I = find(xnorm > maxError);  % for the rest DC is enough
DCrr = sumXX - sum(xsquared(I)); % the errors for the ones where only DC is selected
I = I(randperm(numel(I)));  % permute the elements of I, important only for D0

% to selecte some or all of the basis vectors of the transform
% may be a good idea, i.e. include eye(N) in D0, but we risk that some
% will not be used at all. Here we rather select the first vectors
% initial dictionary, the K random training vectors
D = dictnormalize( X(:,I(1:K)) );

java_access;
timestart = now();
jD = mpv2.SimpleMatrix(D);

tabIT = zeros((noIT/substep),1);
tabPSNR = zeros((noIT/substep),1);
tabNNZ = zeros((noIT/substep),1);  % number of non-zeros
for subiteration = 1:(noIT/substep)
    %
    disp(' ');
    tic;
    % here ex311 calls ilsdla in Java (mpv2.DictionaryLearning)
    % K-SVD use Java only for vector selection
    for substepnumber = 1:substep
        % 1. vector selection, D and jD are current dictionary
        jDD = mpv2.SymmetricMatrix.innerProductMatrix(jD);
        jMP = mpv2.MatchingPursuit(jD, jDD);
        W = zeros(K,L);
        for i = I   % this is those where DC is not enough
            W(:,i) = jMP.vsORMP(X(:,i), int32(maxS), ...
                max(relLim, maxError/xnorm(i)));
        end
        % 2. Dictionary update (K-SVD)
        for k=1:K
            R = X - D*W;
            Ik = find(W(k,:));
            Rk = R(:,Ik) + D(:,k)*W(k,Ik);
            [U,S,V] = svds(Rk,1,'L');
            D(:,k) = U;
            W(k,Ik) = S*V';
        end
        jD = mpv2.SimpleMatrix(D);    % and update jD
    end
    %  use D and W to find new SNR and number of non-zero weights
    nzW = ones(1,L) + sum(W ~= 0);  % the DC componet + W
    R = X(:,I) - D*W(:,I);  % excluding the ones with only DC
    sumRR = DCrr + sum(sum(R.*R));
    newPSNR = 10*log10( ((L*N)*255^2)/sumRR );
    disp([mfile,': ',int2str(subiteration*substep),' iterations:',...
        ' maxError = ',num2str(maxError),...
        ' PSNR = ',num2str(newPSNR),...
        '  sparseness = ',num2str( sum(nzW)/(L*N) ),...
        '  NOF non-zeros is ',int2str(sum(nzW)),'.']);
    timeleft = (ceil(noIT/substep)-subiteration)*(now()-timestart)/subiteration;
    disp(['Time for ',int2str(substep),' iterations is ',num2str(toc),' sec. ', ...
        'Estimated finish time is ',datestr(now()+timeleft)]);
    tabIT(subiteration) = subiteration*substep;
    tabPSNR(subiteration) = newPSNR;
    tabNNZ(subiteration) = sum(nzW);
    %
    % we may want to adjust maxError
    % factor = 1 + 0.1*(1-subiteration/(noIT/substep))*abs(targetPSNR-newSNR);
    factor = 1 + 0.2*((1-subiteration/(noIT/substep))^2)*min(abs(targetPSNR-newPSNR),2);
    if (newPSNR > targetPSNR)
        % we want to select fewer, i.e. increase maxError
        maxError = maxError*factor;
    else
        % we want to select more, i.e. deccrease maxError
        maxError = maxError/factor;
    end
    I = find(xnorm > maxError);  % for the rest DC is enough
    DCrr = sumXX - sum(xsquared(I)); % the errors for the ones where only DC is selected
end
%
dstr = datestr(now());
ResultFile = [mfile,dstr([4:6,1,2,13,14,16,17]),'.mat'];
if (verbose >= 0); disp(['Save results in ',ResultFile]); end;
save(ResultFile, 'D','tabNNZ','tabPSNR','tabIT','ResultFile',...
    'targetPSNR','N','K','L','transform');
%

res = struct('D',D,...
             'tabNNZ',tabNNZ,...
             'tabIT',tabIT,...
             'tabPSNR',tabPSNR,...
             'ResultFile',ResultFile,...
             'targetPSNR',targetPSNR,...
             'N',N,'K',K,'L',L,'transform',transform );


% display some properties for the results
ex31prop(ResultFile);
    
if testLena
    % sparse representation of lena using trained dictionary
    targetPSNRtab = [32, 34, 36, 38];
    r2 = cell(size(targetPSNRtab));
    for i = 1:numel(targetPSNRtab)
        r2{i} = imageapprox(double(imread('lena.bmp'))-128, ...
            'Transform',res.transform, ...
            'Dictionary',res.D, ...
            'targetPSNR',targetPSNRtab(i), ...
            'peak',255, ...
            'delta',0, ...
            'verbose', 1);
    end
    res.r2 = r2;
end
